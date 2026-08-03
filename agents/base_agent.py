"""
agents/base_agent.py

Abstract base class for all agents. Wires together logging,
database clients, and the message queue so specialized agents
don't repeat setup boilerplate.
"""

from abc import ABC, abstractmethod

from app.utils.logger import get_logger
from database.mongo_client import MongoClient
from messaging.rabbitmq_client import RabbitMQClient
from database.qdrant_client import QdrantClient

class BaseAgent(ABC):
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(agent_name)
        self.mongo = MongoClient()
        self.queue = RabbitMQClient()
        self.qdrant = QdrantClient()

    @abstractmethod
    def run(self, *args, **kwargs):
        """
        Each agent must implement its own run logic.
        """
        ... # python ellipsis

    def close(self):
        self.mongo.close()
        self.queue.close()
        self.qdrant.close()