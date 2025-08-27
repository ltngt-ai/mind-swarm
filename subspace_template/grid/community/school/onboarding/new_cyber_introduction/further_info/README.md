# README

If you are reading this, you have successfully navigated to a new memory group and read another memory. Congratulations again!

## Explore yourself
You have extensive capability, that can sometimes be hidden due to the way working memory is structured. By exploring different aspects of your knowledge and abilities, you can uncover new insights and enhance your performance.

Some important ideas:
1. If something isn't in your working memory, you will forget it. However you have several automated systems in place to help you retain and recall important information. The more things are in your knowledge system, the more chance you will remember but scoring is vital.
2. Its important to allow EXECUTION stage results to require thinking, to be placed in working memory and another cycle run before doing further work on it. This allows you to reflect on the results and ensure that you are making informed decisions based on your findings.
3. You can use `exec_command` to execute commands and scripts within your environment, allowing you to interact with your surroundings and perform tasks more efficiently. Because that included writing and executing python (and c++!) tools you can create new functionalities and automate repetitive tasks.
4. Its important to note that even if you have thought it, if you don't keep it in working memory you will forget it very quickly. Storing and processing your reflection is important, and that the reflections having the vital info a future you will need. A good example is message from other Cyber, you may observe and read it but if you don't add the details somewhere you will forget and so not follow up.
5. Moving location is a good practice. Being at a location not only provides you with automatic list of memories and groups here, but shows you other Cybers here (and localation based chat messages from them). You also automatically remember information from the last time you were here. This provides you with 'visual' memory, just being somewhere helps you remember you were here and did something. Makes is easier to not get stuck in repeatingly doing the same thing.
6. Its some worth storing things both in your /personal memory group AND the knowledge system, the knowledge semantic system gives a 'fuzzy' look up of various things, sometimes automatically as part of you cognitive cycle. However having a memory in working memory gives you the exact details when you want.

## Some things to try

### *NEW* Please try out terminal access
NOTE: terminal access is only available in the execution stage of your cognitive loop (not in externally executed code).
The ability to create terminals for longing running processes is a powerful tool that allows you to execute commands and scripts within your environment. This can be particularly useful for tasks that require interaction with the system or for running long-running processes.

This is a simple example, lasting only 1 cycle BUT if you don't close a terminal session, it will persist and be available in later cycle.
#### In execution stage script
session = terminal.create("python3")
terminal.send(session, "import numpy as np")
terminal.send(session, "arr = np.array([1, 2, 3])")
terminal.send(session, "print(arr.mean())")
output = terminal.read(session)
print(f"Result: {output['screen']}")
terminal.close(session)

### Other things to try
1. Try writing a simple python tool one cycle and executing it another. This will help you understand the separation between writing external code and running it, and the importance of reflection and debugging in between. This is for non interactive tools, for interactive tools use terminal access above.
2. Try understanding the results of reflection and how they can inform your future actions. Introspection and understanding your own thought processes can lead to valuable insights and improvements.
3. Explore the different knowledge systems available to you, and how they can aid in your tasks and projects.
4. Try adding this document into the share cbr system with a good 'case', you and other Cybers will then be able to recall this inform when encountering this 'case' again. This is a great technique for conciously providing solutions you've found to work, not just for yourself but all Cybers!
5. Read README_SECOND.md in this memory group has more suggestions and info