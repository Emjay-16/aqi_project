from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

#deploy server
from api.database import Base

# local server
# from database import Base

class Users(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    username = Column(Text, nullable=False)
    email = Column(Text, nullable=False)
    phone = Column(Text, nullable=False)
    password = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False)
    nodes = relationship("Nodes", back_populates="user")
    tokens = relationship("Token", back_populates="user")

class Token(Base):
    __tablename__ = "tokens"
    token_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    verification_token = Column(Text, nullable=False)
    token_expiry = Column(DateTime, nullable=False)
    is_verified = Column(Boolean, default=False)

    user = relationship("Users", back_populates="tokens")

    def is_token_expired(self):
        return datetime.utcnow() > self.token_expiry if self.token_expiry else False
    
class Nodes(Base):
    __tablename__ = "nodes"
    node_id = Column(Text, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    node_name = Column(Text, nullable=False)
    location = Column(Text, nullable=False)
    description = Column(Text, nullable=False)

    user = relationship("Users", back_populates="nodes")
    