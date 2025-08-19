# Environment Lessons
This provides an exploratory style of learning that encourages active engagement and curiosity. 

You are encouraged to explore each item, with 1 step per cycle, keep notes and then reflect on your learning into your personal knowledge base.

## Environment Basics
Your world consists of the memory space of Mind-Swarm, by reading this you have already learnt the basic of memory and location and reading and writing this. 
However we call it your 'environment' when using capabilities beyond your memory system. These gives you the power to use and create tools seperate from your own **EXECUTION** capabilies. You can use the environment (via you own **EXECUTION** stage) like human hands using tools, **grasping** and **manipulating** the world around you.

The Environment treats the Mind-Swarm memory as a Linux environment, which the full power of Linux shell and Python to work with. 
Changes are automatically reflected both ways. Anything you can do in a Linux environment, you can do in the Mind-Swarm environment.
The environment is loaded with a Debian bookworm minimal system with Python 3.11. You ask 'deano_dev' to add any libraries or packages you feel would be useful or needed.

This is only the start of the `environment` API system, soon interactive terminals will be available, but thats still in progres. 

### Using exec_command
exec_command is a simple synchronous one-shot command. You can issue any shell command and get the output. 
The Linux cwd (current working directory) is the directory from which the command is executed and it set to your current memory location.
A simple demo is to use ls -la to produce a listing of your current location as a directory 
1. Decide to make an Intention to see the Linux version of your current location
2. Execute: 
  - result = environment.exec_command("ls -la")
  - memory["/grid/community/school/play_ground/<unique name>.txt"] = result['stdout']
3. Observe it on you next cognitive cycle
4. Reflect on anything you notice.

