from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False) # Added
    hashed_password = Column(String, nullable=False) # New field for auth
    age = Column(Integer, nullable=True) # made optional as risk/goals are now in onboarding
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    portfolio_items = relationship("PortfolioItem", back_populates="owner")

class PortfolioItem(Base):
    """
    Represents a local cache of the user's portfolio or performed trades.
    Actual execution happens via Alpaca, but we track it here for the record.
    """
    __tablename__ = "portfolio_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    asset_symbol = Column(String, nullable=False) # e.g., "AAPL", "BTC/USD"
    asset_type = Column(String, nullable=False) # "Stock", "Crypto", "ETF"
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="portfolio_items")

class Onboarding(Base):
    """
    Stores user's onboarding questionnaire responses and the derived profile.
    """
    __tablename__ = "onboarding"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    answers = Column(String, nullable=False) # JSON string of answers
    derived_profile = Column(String, nullable=True) # JSON string of calculated profile
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="onboarding")

# Backfill User relationship
User.onboarding = relationship("Onboarding", back_populates="user", uselist=False)
