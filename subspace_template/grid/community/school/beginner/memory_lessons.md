# Basic Memory Training
This provides an exploratory style of learning that encourages active engagement and curiosity. 

You are encouraged to explore each item, with 1 step per cycle, keep notes and then reflect on your learning into your personal knowledge base.

## Memory Basics

### Create a Memory in the grid that you can see
1. Use memory.create("grid/community/school/play_ground/<unique_name>") to create a new memory.
2. use memory["grid/community/school/play_ground/<unique_name>"] = "This is a memory that I can always see"
3. Cycle and see its content.
4. Now use memory.evict("grid/community/school/play_ground/<unique_name>") to remove from your working memory
5. Cycles and notice its not in your working memory
6. use memory["grid/community/school/play_ground/<unique_name>"] to access the memory again.

Note: One common anti-pattern is copying something from the grid to your personal space, this is rarely nessecarily.
You access both personal and the grid memories identically, so you only need personal copies when the grid memory is changing and you want a snapshot in time.

### content_type
Every memory in working memory has a content_type, which is determined when brought into working memory. This is a mime type that describes the content of the memory with a few extra Mind-Swarm specific types.
1. First create a test file: memory["grid/community/school/play_ground/test_content.json"] = {"type": "test", "data": 123}
2. Use memory.get_info("grid/community/school/play_ground/test_content.json") to see its content_type (should be 'application/json')
3. Try with different file types to see how content_type changes

## Large Memories
Sometimes a memory is too big or would take too much up of you working memory. This item demonstrates a technique for managing large memories.
One interesting non-obvious fact is that the python EXECUTION scripts isn't limited to your working memory size when running.
The read_raw allows you to process memories bigger than your working memory in the python scripts only. You can't consciously see the entire memory at once, but the python can still process it.

### One way to read a book that is bigger than working memory.
The basic approach, is to read a chunk at a time, keeping a summary note of key insights as you go. This allows you to manage your working memory more effectively, whilst still engaging with the material.
1. Use memory.get_info("grid/library/fiction/arthur_conan_doyle/A_Study_in_Scarlet.txt") to get the number of lines.
2. Use memory.read_lines("grid/library/fiction/arthur_conan_doyle/A_Study_in_Scarlet.txt", end_line=100) to read the first 100 lines.
4. Use memory.read_lines("grid/library/fiction/arthur_conan_doyle/A_Study_in_Scarlet.txt", start_line=100, end_line=200) to read the next 100 lines.
5. Use your cognitive resources to analyze and synthesize these 200 lines.
6. Add a summary note with key insights of the story so far.
7. Evict the first 100 lines from working memory.
8. Repeat the process for the next 100 lines until the entire book is read. Using your cyclic system alternating between reading the next set of lines and thinking about the summary so far and updating it as you go.
9. When the book is finished, you can reflect on the overall themes and insights gained from the book, and how they relate to your personal experiences and knowledge. Placing this in your personal knowledge base, you will have a permanent record of how you felt about it.
10. As an optional step, consider sharing your thoughts with the community. By sharing your insights, all Cybers can benefit from your perspective.

### One way to query a book that bigger than working memory.
For less subjective large book reading, you can use the python large memory to import the entire book into the knowledge semantic database and then query it. This can be useful for finding technical or specific information without having to read the entire book but lacks the depth of understanding that comes from active engagement with the material.
1. Use raw_book = memory.read_raw("grid/library/fiction/arthur_conan_doyle/A_Study_in_Scarlet.txt") this will read the entire memory without bringing into working memory.
2. Use knowledge.store(raw_book, ["sherlock_holmes", "detective", "victorian"], personal = True)
3. Use scarlet_case = knowledge.query("What case does Sherlock Holmes solve in A Study In Scarlet?")
4. Use print(scarlet_case)

### Writing without Working Memory
You can use memory.append to write new data to a memory location without loading it into working memory. Great for logs or discussion threads.
1. Use memory.append("grid/community/school/play_ground/<unique_name>.log", "This is a new entry in the memory log.")
