from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Float, Unicode
from sqlalchemy.ext.declarative import declarative_base
 
engine = create_engine('sqlite:///queue.db', echo=True)
Base = declarative_base()
 
 
class Task(Base):
    __tablename__ = "tasks"
 
    id = Column(Integer, primary_key=True)
    owner = Column(String)
    task_type = Column(String)
    duration = Column(Integer)
    program = Column(String)
    status = Column(String)
 
    def __repr__(self):
        return "%s - %10s - id: %s"%(self.owner, self.task_type, self.id)
  
# create tables
Base.metadata.create_all(engine)
