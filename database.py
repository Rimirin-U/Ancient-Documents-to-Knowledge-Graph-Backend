"""
数据库初始化模块
"""
import os
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import create_engine, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, mapped_column, Mapped

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


class OcrStatus(str, Enum):
    """状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class User(Base):
    """用户表"""
    __tablename__ = "user"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 关系
    images = relationship("Image", back_populates="user")


class Image(Base):
    """图像表"""
    __tablename__ = "image"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    upload_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="images")
    ocr_results = relationship("OcrResult", back_populates="image")
    document = relationship("Document", back_populates="image", uselist=False)


class OcrResult(Base):
    """OCR结果表"""
    __tablename__ = "ocr_result"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("image.id"), index=True)
    raw_text: Mapped[str] = mapped_column(String)
    status: Mapped[OcrStatus] = mapped_column(SQLEnum(OcrStatus), default=OcrStatus.PROCESSING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    
    # 关系
    image = relationship("Image", back_populates="ocr_results")


class Document(Base):
    """
    文档分析结果表
    存储从OCR文本中提取的结构化信息
    """
    __tablename__ = "document"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("image.id"), unique=True)
    
    # 解析内容
    time_text: Mapped[str] = mapped_column(String, nullable=True)
    time_ad: Mapped[int] = mapped_column(Integer, index=True, nullable=True) # 公元年份
    location: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[str] = mapped_column(String, nullable=True)
    subject: Mapped[str] = mapped_column(Text, nullable=True)
    translation: Mapped[str] = mapped_column(Text, nullable=True)
    
    # 关系
    relations = relationship("Relation", back_populates="document", cascade="all, delete-orphan")
    image = relationship("Image", back_populates="document")


class Entity(Base):
    """
    实体表
    存储从文档中提取的人、地点、组织等实体
    """
    __tablename__ = "entity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String) # person, organization, location, object, date
    
    # 用于实体消歧的元数据
    first_seen_year: Mapped[int] = mapped_column(Integer, nullable=True)
    last_seen_year: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # 关系
    relations = relationship("Relation", back_populates="entity", cascade="all, delete-orphan")


class Relation(Base):
    """
    关系表
    连接文档和实体，并定义角色
    """
    __tablename__ = "relation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("document.id"))
    entity_id: Mapped[int] = mapped_column(Integer, ForeignKey("entity.id"))
    role: Mapped[str] = mapped_column(String) # Seller, Buyer, Middleman, Witness, Subject, etc.
    
    document = relationship("Document", back_populates="relations")
    entity = relationship("Entity", back_populates="relations")


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
