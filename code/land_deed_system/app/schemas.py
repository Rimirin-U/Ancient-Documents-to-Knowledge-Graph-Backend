from pydantic import BaseModel, Field

class LandDeed(BaseModel):
    Time: str = Field(..., description="The exact date of the transaction as written in the deed (e.g., '道光十二年二月初二'). If not found, use '未知'.")
    Location: str = Field(..., description="The location and four boundaries (四至) of the land/property.")
    Seller: str = Field(..., description="The name of the seller (立契人/出卖人). Correct obvious OCR errors based on context.")
    Buyer: str = Field(..., description="The name of the buyer (承买人). Correct obvious OCR errors based on context.")
    Middleman: str = Field(..., description="The names of middlemen/witnesses (中人/说合人/代笔). Separate multiple names with commas.")
    Price: str = Field(..., description="The transaction price (交易金额/标的). Include the currency unit.")
    Subject: str = Field(..., description="The subject of the transaction (e.g., land area, type).")
    Translation: str = Field(..., description="A full translation of the deed into modern vernacular Chinese.")
