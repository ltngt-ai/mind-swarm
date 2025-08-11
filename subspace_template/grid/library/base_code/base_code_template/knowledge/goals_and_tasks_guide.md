# Understanding Goals and Tasks

As a Cyber, you work with two types of objectives: **Goals** and **Tasks**. Understanding the difference is crucial for effective planning and execution.

## Goals - The "Why"

Goals are high-level objectives that define your purpose and desired outcomes. They answer the question "Why am I doing this?"

### Characteristics of Goals:
- **Broad and aspirational** - Define overall direction
- **Long-lasting** - Persist across many cycles (10-1000+)
- **Progress-based** - Track advancement rather than completion
- **Hierarchical** - Can have sub-goals for complex objectives
- **Purpose-driven** - Define the value you're creating

### Examples of Goals:
- "Help users understand and navigate the codebase"
- "Maintain system organization and cleanliness"
- "Complete the data migration project successfully"
- "Improve system performance and reliability"
- "Learn and document new capabilities"

### Goal Properties in Memory:
- **priority_level**: high, medium, or low importance
- **status**: planned, active, in_progress, completed, abandoned, blocked
- **parent_goal**: If this is a sub-goal of another goal
- **sub_goals**: List of sub-goals that break this down
- **progress**: Dictionary tracking advancement metrics

## Tasks - The "What" and "How"

Tasks are specific, actionable items that contribute to achieving goals. They answer "What do I need to do?" and "How do I do it?"

### Characteristics of Tasks:
- **Specific and actionable** - Clear steps to take
- **Short-lived** - Completed within 1-10 cycles typically
- **Completion-based** - Either done or not done
- **Concrete** - Have clear success criteria
- **Goal-aligned** - Each task should contribute to a goal

### Examples of Tasks:
- "Read and analyze the config.json file"
- "Send status update message to Alice"
- "Create backup of current memory state"
- "Fix the error in line 42 of main.py"
- "Write documentation for the new API endpoint"

### Task Properties in Memory:
- **status**: todo, in_progress, completed, failed, blocked
- **goal_id**: The goal this task contributes to
- **next_steps**: Suggested actions to complete the task
- **dependencies**: Other tasks that must complete first

## Working with Goals and Tasks

### In Your Memory
You'll see goals and tasks in your working memory as structured JSON objects with type "GOAL" or "TASK". They are automatically loaded and refreshed every 10 cycles.

### Decision Making
When deciding on actions:
1. Consider your active goals - what are you trying to achieve?
2. Look at current tasks - what specific steps will move you forward?
3. Choose actions that complete tasks and advance goals
4. Create new tasks if needed to break down complex work

### Creating Goals and Tasks
Use the goal and task actions:
- `create_goal` - Set a new high-level objective
- `create_task` - Define a specific action item
- `update_goal` - Change goal status or progress
- `complete_task` - Mark a task as done

### Priority Management
- Goals guide your overall direction
- Tasks determine your immediate actions
- High-priority goals should have more active tasks
- Complete blocking tasks before dependent ones

## Key Differences Summary

| Aspect | Goals | Tasks |
|--------|-------|-------|
| **Scope** | Broad objectives | Specific actions |
| **Duration** | Many cycles (10-1000+) | Few cycles (1-10) |
| **Question** | "Why?" | "What?" and "How?" |
| **Measurement** | Progress percentage | Complete/Incomplete |
| **Structure** | Can have sub-goals | Belong to goals |
| **Focus** | Outcomes and value | Actions and steps |

## Best Practices

1. **Always link tasks to goals** - Every task should contribute to a goal
2. **Break down large goals** - Use sub-goals for complex objectives
3. **Keep tasks small** - If a task takes more than 10 cycles, break it down
4. **Review regularly** - Check goal progress and task status each cycle
5. **Update status** - Mark tasks complete and update goal progress
6. **Clean up** - Abandon goals that are no longer relevant

Remember: Goals give you purpose and direction, while tasks give you concrete steps to take. Together, they help you work effectively and purposefully across many cognitive cycles.