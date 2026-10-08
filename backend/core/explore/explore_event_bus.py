# # core/explore/explore_event_bus.py

# import asyncio
# from collections import defaultdict


# class ExploreEventBus:

#     def __init__(self):
#         self._queues: dict[int, set[asyncio.Queue]] = defaultdict(set)

#     async def subscribe(self, user_id: int):
#         queue = asyncio.Queue()

#         self._queues[user_id].add(queue)

#         try:
#             while True:
#                 event = await queue.get()
#                 yield event

#         finally:
#             self._queues[user_id].discard(queue)

#             if not self._queues[user_id]:
#                 del self._queues[user_id]

#     async def publish(self, user_id: int, event: dict):
#         for queue in self._queues.get(user_id, set()):
#             await queue.put(event)


# explore_event_bus = ExploreEventBus()