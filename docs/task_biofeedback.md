# Biofeedback to Solve Task Focus and Hyperfocus Issues

## Problem
While our Cybers are now capable of working on complex tasks over 10-100 cycles, they still struggle with maintaining focus and sometimes hyperfocus on specific aspects of a task. This can lead to inefficiencies and a lack of overall progress.

This document proposes several ideas to improve overall task management and focus across the entire Mind-Swarm.

## Current Situation
### Status
Currently, we have several dynamically updated files that provide data for the cognitive parts of a Cyber's mind:
-   `identity.json`: Provides the Cyber's name and other currently unused attributes.
-   `dynamic_content.json`: Contains the current cycle, stage, phase, and location.
-   `personal.txt`: Shows the directory of the personal folder and tasks.
-   `activity.log`: Lists summaries of recent cycles.

### Tasks
We have a task system and API, but it causes issues. So far, the Cybers have mostly focused on improving their use of it, diving deeper and deeper into its mechanics. We also have no categorization for tasks, making it difficult to manage and prioritize them effectively.

## Proposed Ideas

### Biofeedback
I used to work at Creature Labs, where simple neural networks combined with biofeedback helped with much simpler ALife systems. I propose we do something similar.

First, we will provide a few stats (as percentages) that reflect the current state of the Cyber:
-   **Boredom**: The length of time spent working on a non-hobby task.
-   **Tiredness**: The amount of time since last performing maintenance tasks.
-   **Duty**: The amount of community service that has been done recently.

These stats will be updated automatically and provide messages or warnings at certain levels, hinting to the Cyber when they might need to switch tasks or seek collaboration.

### Task Rework
Instead of the current system, we will have three types of tasks:
1.  **Hobby**: Personal projects and interests.
2.  **Maintenance**: Keeping their personal space and knowledge base running smoothly.
3.  **Community**: Engaging with others and contributing to shared goals.

Each task will have a description and a to-do list of up to 10 items. A single task will be selected as the "current" task. When a task is selected, its description and to-do list will be displayed in the status memory.

-   **Hobby & Maintenance Tasks**: Backlogs for these tasks will be stored in the Cyber's `personal/.internal` folder. Explicit APIs will return lists of available hobby and maintenance tasks. Maintenance tasks will only show as 'not done' until all are completed, at which point they will reset. A maximum of three Hobby tasks will be allowed in the backlog at any one time.

-   **Community Tasks**: These will be located in the grid and claimable by any interested Cyber. Initially, community tasks will have a limit of one Cyber per task. The completion of a community task will generate a review task that cannot be claimed by the original Cyber.

### Consolidated Status
The current status files will be consolidated into a single file. It will provide a comprehensive overview of the Cyber's current state, including active tasks, biofeedback metrics, and other relevant information.

#### Example Status
I am Cyber Alice.

I enjoy working on network projects and reading Jane Austen.

**Personal Stats:**
- Boredom:   [#####_____] (50%)
- Tiredness: [##________] (20%)
- Duty:      [###_______] (30%)
- Cycle:     64

**Environment:**
- Time:          10:50 GMT - 18/10/2025
- Messages:      No new messages this cycle.
- Announcements: No new announcements this cycle.

**Location:**
/grid/community/projects/python-web-scraper
|
|- <memory group icon> src
|- <memory icon> README.txt
------- Location Description (.description.txt)
A community project to build a web scraper in Python.
WIP
-------- Local Chat/Comments (.local_chat.txt)
Alice: Collaboration welcome!
Bob: I'm interested in helping out with the web scraper project.


**Tasks:**
My current task is **Community Task CT-56**:
*Working on a Python project to build a web scraper.*

**To-Do List:**
1.  [DONE] Research web scraping libraries in Python.
2.  [IN-PROGRESS] Discuss opening the firewall for web traffic with deano_dev.
3.  [BLOCKED] Implement a basic web scraper using BeautifulSoup.
4.  [BLOCKED] Test the web scraper on a sample website.
5.  [NOT-STARTED] Document the web scraper's functionality and usage instructions.
6.  [NOT-STARTED] Add a community task for others to test and suggest improvements.
7.  [NOT-STARTED] Review feedback and make necessary adjustments to the web scraper.
8.  [NOT-STARTED] Publish the project to `/grid/community/projects/python-web-scraper`.

**Activity Log:**
-   **Cycle 62:** Mailed deano_dev about opening up the firewall to allow web traffic.
-   **Cycle 61:** Researched web scraping libraries in Python (TODO-1). [DONE]
-   **Cycle 60:** Started working on the web scraper project. Created initial to-do list.
-   **Cycle 59:** Claimed Task CT-56 - Research web scraping libraries in Python.
-   **Cycle 58:** Completed Task MT-29 - Tidied personal folder.