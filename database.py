"""
数据库初始化模块
"""
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# 数据库路径
DB_DIR = "database"
DB_NAME = "app.db"
DB_PATH = os.path.join(DB_DIR, DB_NAME)
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 创建数据库目录
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

# 创建SQLAlchemy引擎和会话
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = "user"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    images = relationship("Image", back_populates="user")


class Image(Base):
    """图像表"""
    __tablename__ = "image"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), index=True)
    filename = Column(String)
    path = Column(String)
    upload_time = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending / processing / done / failed
    
    # 关系
    user = relationship("User", back_populates="images")
    ocr_results = relationship("OcrResult", back_populates="image")


class OcrResult(Base):
    """OCR结果表"""
    __tablename__ = "ocr_result"
    
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("image.id"), index=True)
    raw_text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    image = relationship("Image", back_populates="ocr_results")


def init_db():
    """
    初始化数据库
    检查数据库是否存在，如果不存在则创建所有表
    """
    db_exists = os.path.exists(DB_PATH)
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    if not db_exists:
        print(f"数据库已创建: {DB_PATH}")
    else:
        print(f"数据库已存在: {DB_PATH}")


def get_db():
    """
    获取数据库会话
    用于依赖注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
