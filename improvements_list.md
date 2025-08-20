# List of things to do to improve based on previous runs
Mark items as DONE or IN_PROGRESS with developer (deano or Claude)
Some are complex and need plan and discussion.

## List of current improvement ideas
1. Remove I/O Cybers - not used currently and not sure if will be. remove cleanup code
2. Redo Cyber identity.json - replace with type and capabilaties, and use a md file more prescriptive. "I am a Cyber called Alice"
3. Improvement educational material (IN_PROGRESS - deano)
4. Add location based memory - Cybers remember the last thing they did at a location, providing 'visual memory'. Shown when they at that location (DONE - Claude)
5. Examine the current memory and knowledge complexity and see confusing and too many options
6. Refactor memory types, we only have 1 now, let tidy up to what it actuall used now. (DONE - Claude)
7. Remove vestigical local llm support
8. Add a /personal/activity.log - single line description per cycle (reflect can generate) with a cycle count. Have last 10 entries shown automatically
9. Current goals + tasks aren't defined very well, provide Cyber API for consistency. Starter cyber goal+task shouldn't be in code
10. Add a projects folder to the grid. move cyber base code into a folder in here. Future plan is this is where Cybers work collaboratively on projects.
11. Add per-location .local_chat.json that is added when Cyber's use a new communication API communication.local_chat(), current location.txt will show the latest 5 messages, adding local spatial quick chat/disccusions.
12. Message history is a problem - prehaps we need to show N last messages? This comes back to the issue of medium/long term memory. We have a semantic database but what to store and how to score it AND when to retrieve is still a big issue... Semantic message by dates? On new message received load it and any similar? (DONE - Claude: Messages now automatically stored in semantic memory, related messages shown with new ones)
13. Is memory.content auto parsing useful or just confusing? Cybers have access to a python environment, we can give them access content determination via magic and let them decide what is is and parse via common json and yaml. Is providing a 'helper' actually confusing?