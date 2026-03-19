"""图片路由：上传 / 获取 / 缩略图 / 删除 / 信息 / 触发OCR"""
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from PIL import Image as PILImage, UnidentifiedImageError
from sqlalchemy.orm import Session

from database import (
    Image,
    MultiTaskStructuredResult,
    OcrResult,
    RelationGraph,
    StructuredResult,
    User,
    get_beijing_time,
    get_db,
)
from app.core.config import settings
from app.core.logger import get_logger
from app.core.security import security, verify_token
from app.worker.tasks import task_ocr_image

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/images", tags=["图片管理"])


def _build_thumbnail_path(filename: str) -> str:
    stem, _ = os.path.splitext(filename)
    return os.path.join(settings.THUMBNAIL_DIR, f"{stem}_thumb.jpg")


def _ensure_thumbnail(image_path: str, thumbnail_path: str) -> None:
    if os.path.exists(thumbnail_path):
        return
    try:
        with PILImage.open(image_path) as img:
            rgb_img = img.convert("RGB")
            rgb_img.thumbnail(settings.THUMBNAIL_SIZE)
            rgb_img.save(thumbnail_path, format="JPEG", quality=settings.THUMBNAIL_QUALITY, optimize=True)
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="无法识别的图片格式")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成缩略图失败: {str(e)}")


@router.post("/upload")
async def upload_image(
    image: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    payload = verify_token(credentials.credentials)
    user_id = payload.get("user_id")

    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        return {
            "success": False,
            "message": f"不支持的文件类型。允许的类型: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        }

    try:
        file_data = await image.read()
    except Exception as e:
        return {"success": False, "message": f"读取文件失败: {str(e)}"}

    file_size = len(file_data)
    if file_size > settings.MAX_FILE_SIZE:
        return {
            "success": False,
            "message": f"文件过大。最大允许 10MB，当前 {file_size / 1024 / 1024:.2f}MB",
        }
    if file_size == 0:
        return {"success": False, "message": "文件为空"}

    original_name = os.path.splitext(image.filename or "upload")[0]
    unique_filename = f"{original_name}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buf:
            buf.write(file_data)
    except Exception as e:
        return {"success": False, "message": f"保存文件失败: {str(e)}"}

    try:
        db_image = Image(
            user_id=user_id,
            filename=unique_filename,
            path=file_path,
            upload_time=get_beijing_time(),
        )
        db.add(db_image)
        db.commit()
        db.refresh(db_image)

        logger.info("image_uploaded", extra={"image_id": db_image.id, "user_id": user_id, "size": file_size})

        return {
            "success": True,
            "imageId": db_image.id,
            "filename": db_image.filename,
            "originalName": image.filename,
            "fileSize": file_size,
            "pipeline_started": True,
        }
    except Exception as e:
        db.rollback()
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        return {"success": False, "message": f"保存到数据库失败: {str(e)}"}


@router.get("/{image_id}")
async def get_image(
    image_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    verify_token(credentials.credentials)
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="image not found")
    if not os.path.exists(str(db_image.path)):
        raise HTTPException(status_code=404, detail="image file not found")
    return FileResponse(str(db_image.path))


@router.get("/{image_id}/thumbnail")
async def get_thumbnail(
    image_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    verify_token(credentials.credentials)
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="image not found")
    if not os.path.exists(str(db_image.path)):
        raise HTTPException(status_code=404, detail="image file not found")

    thumbnail_path = _build_thumbnail_path(db_image.filename)
    _ensure_thumbnail(str(db_image.path), thumbnail_path)
    return FileResponse(thumbnail_path, media_type="image/jpeg")


@router.get("/{image_id}/info")
async def get_image_info(
    image_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    verify_token(credentials.credentials)
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="image not found")

    return {
        "success": True,
        "data": {
            "id": db_image.id,
            "filename": db_image.filename,
            "upload_time": db_image.upload_time.isoformat(),
            "title": "title_test",
        },
    }


@router.delete("/{image_id}")
async def delete_image(
    image_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    payload = verify_token(credentials.credentials)
    user_id = payload.get("user_id")

    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="image not found")
    if db_image.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除该图片")

    original_path = str(db_image.path)
    thumbnail_path = _build_thumbnail_path(db_image.filename)

    structured_ids_query = (
        db.query(StructuredResult.id)
        .join(OcrResult, StructuredResult.ocr_result_id == OcrResult.id)
        .filter(OcrResult.image_id == image_id)
    )

    deleted_ocr_count = db.query(OcrResult).filter(OcrResult.image_id == image_id).count()
    deleted_struct_count = (
        db.query(StructuredResult)
        .join(OcrResult, StructuredResult.ocr_result_id == OcrResult.id)
        .filter(OcrResult.image_id == image_id)
        .count()
    )
    deleted_graph_count = (
        db.query(RelationGraph)
        .filter(RelationGraph.structured_result_id.in_(structured_ids_query))
        .count()
    )
    deleted_assoc_count = (
        db.query(MultiTaskStructuredResult)
        .filter(MultiTaskStructuredResult.structured_result_id.in_(structured_ids_query))
        .count()
    )

    try:
        db.query(MultiTaskStructuredResult).filter(
            MultiTaskStructuredResult.structured_result_id.in_(structured_ids_query)
        ).delete(synchronize_session=False)
        db.query(RelationGraph).filter(
            RelationGraph.structured_result_id.in_(structured_ids_query)
        ).delete(synchronize_session=False)
        db.query(StructuredResult).filter(
            StructuredResult.id.in_(structured_ids_query)
        ).delete(synchronize_session=False)
        db.query(OcrResult).filter(OcrResult.image_id == image_id).delete(synchronize_session=False)
        db.delete(db_image)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除图片失败: {str(e)}")

    removed_files: List[str] = []
    for path in (original_path, thumbnail_path):
        try:
            if os.path.exists(path):
                os.remove(path)
                removed_files.append(path)
        except OSError:
            pass

    logger.info("image_deleted", extra={"image_id": image_id, "user_id": user_id})

    return {
        "success": True,
        "message": "图片及关联分析结果已删除",
        "deleted": {
            "image_id": image_id,
            "ocr_results": deleted_ocr_count,
            "structured_results": deleted_struct_count,
            "relation_graphs": deleted_graph_count,
            "multi_task_associations": deleted_assoc_count,
            "removed_files": removed_files,
        },
    }


@router.post("/{image_id}/ocr")
async def trigger_ocr(
    image_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    verify_token(credentials.credentials)
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    task_ocr_image.delay(image_id)
    logger.info("ocr_triggered", extra={"image_id": image_id})

    return {"success": True, "message": f"图片 {image_id} 的OCR任务已提交到队列"}


@router.get("/{image_id}/ocr-results")
async def get_image_ocr_results(
    image_id: int,
    skip: int = 0,
    limit: int = 10,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    verify_token(credentials.credentials)
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    ocr_results = (
        db.query(OcrResult.id)
        .filter(OcrResult.image_id == image_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(OcrResult).filter(OcrResult.image_id == image_id).count()

    return {
        "success": True,
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "ids": [r[0] for r in ocr_results],
        },
    }
