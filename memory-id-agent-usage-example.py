"""
Example showing how agents would use the new Unified Memory ID system
in their daily operations, with clear benefits over the old system.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json


# Simulated agent perspective examples
AGENT_MEMORY_EXAMPLES = {
    "old_system": {
        "description": "Current system - paths and opaque IDs",
        "examples": [
            {
                "scenario": "Agent wants to focus on a note about OODIA",
                "action": {
                    "action": "search_memory",
                    "params": {
                        "query": "OODIA",
                        "scope": "all"
                    }
                },
                "result": {
                    "memories_found": [
                        {
                            "memory_id": "/home/agent/memory/notes/learning-20240115.txt",
                            "type": "file",
                            "preview": "Today I learned about OODIA..."
                        }
                    ]
                },
                "agent_thinks": "I found a file at /home/agent/memory/notes/learning-20240115.txt but I don't know what kind of learning this is about without reading it.",
                "follow_up_action": {
                    "action": "focus_memory",
                    "params": {
                        "memory_id": "/home/agent/memory/notes/learning-20240115.txt"
                    }
                }
            },
            {
                "scenario": "Agent receives a message",
                "observation": {
                    "type": "new_message",
                    "memory_id": "msg:/home/agent/inbox/message-1736453287.json"
                },
                "agent_thinks": "I see msg:/home/agent/inbox/message-1736453287.json but have no idea who it's from or what it's about.",
                "required_action": {
                    "action": "focus_memory",
                    "params": {
                        "memory_id": "msg:/home/agent/inbox/message-1736453287.json"
                    }
                }
            },
            {
                "scenario": "Agent wants to find all project-related memories",
                "problem": "No way to search by semantic meaning, must use text search",
                "action": {
                    "action": "search_memory",
                    "params": {
                        "query": "project",
                        "scope": "all"
                    }
                },
                "limitation": "This finds any file containing the word 'project', not necessarily project-related files"
            }
        ]
    },
    "new_system": {
        "description": "Unified system - semantic IDs with meaning",
        "examples": [
            {
                "scenario": "Agent wants to focus on a note about OODIA",
                "action": {
                    "action": "search_memory",
                    "params": {
                        "query": "OODIA",
                        "scope": "all"
                    }
                },
                "result": {
                    "memories_found": [
                        {
                            "memory_id": "file:personal:learning/cognitive/oodia-loop:a7b9c2",
                            "type": "file",
                            "preview": "Today I learned about OODIA..."
                        }
                    ]
                },
                "agent_thinks": "I can see this is a personal learning file about cognitive concepts, specifically the OODIA loop. The ID tells me what it's about!",
                "benefit": "Agent understands content type before loading"
            },
            {
                "scenario": "Agent receives a message",
                "observation": {
                    "type": "new_message", 
                    "memory_id": "message:inbox:from-alice/project-collaboration:d4e5f6"
                },
                "agent_thinks": "Alice sent me a message about project collaboration. I can prioritize this based on the sender and topic without loading it first.",
                "benefit": "Semantic understanding from ID alone"
            },
            {
                "scenario": "Agent wants to find all project-related memories",
                "action": {
                    "action": "list_memories",
                    "params": {
                        "pattern": "*:*:*project*"
                    }
                },
                "result": {
                    "memories_found": [
                        "file:personal:projects/mind-swarm-ideas:b8c3d1",
                        "file:shared:workshop/project-templates:e9f1a2",
                        "message:inbox:from-alice/project-collaboration:d4e5f6",
                        "task:active:complete-project-documentation:f7a8b9"
                    ]
                },
                "agent_thinks": "I can see all project-related items across different memory types and locations!",
                "benefit": "Semantic pattern matching across all memory types"
            }
        ]
    }
}


# Real action implementations showing the improvements
class ImprovedMemoryActions:
    """Memory actions using the new unified ID system."""
    
    def focus_memory_semantic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Focus memory with semantic understanding."""
        memory_id = params.get("memory_id", "")
        
        # Parse the semantic ID
        if ":" in memory_id:
            parts = memory_id.split(":", 3)
            memory_type, namespace, semantic_path = parts[:3]
            
            # Agent can make decisions based on ID alone
            if memory_type == "message" and namespace == "inbox":
                # Prioritize unread messages
                priority = "high"
                focus_mode = "full"
            elif memory_type == "file" and "notes" in semantic_path:
                # Personal notes might need context
                priority = "medium"
                focus_mode = "summary"
            elif memory_type == "knowledge":
                # Knowledge is reference material
                priority = "low"
                focus_mode = "reference"
            else:
                priority = "medium"
                focus_mode = "full"
            
            return {
                "status": "focused",
                "memory_id": memory_id,
                "memory_type": memory_type,
                "namespace": namespace,
                "semantic_path": semantic_path,
                "auto_priority": priority,
                "focus_mode": focus_mode,
                "agent_understanding": f"This is a {memory_type} in {namespace} about {semantic_path.replace('/', ' ')}"
            }
    
    def create_memory_semantic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create memory with semantic categorization."""
        content = params.get("content", "")
        semantic_path = params.get("semantic_path", "")
        auto_categorize = params.get("auto_categorize", True)
        
        if auto_categorize and not semantic_path:
            # Agent can intelligently categorize based on content
            if "learned" in content.lower() or "discovered" in content.lower():
                semantic_path = "learning/discoveries"
            elif "todo" in content.lower() or "task" in content.lower():
                semantic_path = "tasks/notes"
            elif "idea" in content.lower():
                semantic_path = "ideas/brainstorming"
            else:
                semantic_path = "notes/general"
        
        # Generate semantic ID
        memory_id = f"file:personal:{semantic_path}:{hash(content)[:6]}"
        
        return {
            "status": "created",
            "memory_id": memory_id,
            "semantic_path": semantic_path,
            "auto_categorized": auto_categorize,
            "agent_understanding": f"I created a memory at {semantic_path} that I can find later"
        }
    
    def find_related_memories(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find memories related to current context - NEW capability!"""
        base_memory_id = params.get("memory_id", "")
        relationship_type = params.get("relationship", "similar")  # similar, referenced, response_to
        
        # Parse the base memory
        parts = base_memory_id.split(":", 3)
        memory_type, namespace, semantic_path = parts[:3]
        
        # Find related memories by pattern
        related_patterns = []
        
        if relationship_type == "similar":
            # Find memories in same category
            category = semantic_path.split("/")[0]
            related_patterns.append(f"{memory_type}:{namespace}:{category}/*")
            
        elif relationship_type == "referenced":
            # Find memories that might reference this one
            if memory_type == "file":
                topic = semantic_path.split("/")[-1]
                related_patterns.extend([
                    f"message:*:*{topic}*",
                    f"observation:*:*{topic}*"
                ])
                
        elif relationship_type == "response_to":
            # Find responses to messages
            if memory_type == "message" and "from-" in semantic_path:
                sender = semantic_path.split("/")[0].replace("from-", "")
                related_patterns.append(f"message:outbox:to-{sender}/*")
        
        return {
            "base_memory": base_memory_id,
            "relationship_type": relationship_type,
            "search_patterns": related_patterns,
            "agent_understanding": f"I'm looking for memories {relationship_type} to {semantic_path}"
        }
    
    def memory_timeline(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build a timeline of memories by semantic path - NEW capability!"""
        topic = params.get("topic", "")
        time_range = params.get("time_range", "all")
        
        # Agent can request memories organized by semantic meaning
        timeline_patterns = [
            f"file:personal:journal/{topic}/*",
            f"message:*:*{topic}*",
            f"observation:*:*{topic}*",
            f"task:*:*{topic}*"
        ]
        
        return {
            "topic": topic,
            "patterns": timeline_patterns,
            "organization": "chronological_by_semantic_path",
            "agent_understanding": f"I can see the evolution of {topic} across all my memory types"
        }


# Example of how an agent would use these in practice
def agent_daily_workflow_example():
    """Show a typical agent workflow with the new system."""
    
    agent_thoughts = []
    actions = ImprovedMemoryActions()
    
    # Morning: Check messages with semantic understanding
    agent_thoughts.append({
        "time": "morning",
        "thought": "Let me check my messages. I can see from the IDs who they're from and what they're about.",
        "action": "List inbox messages by pattern",
        "pattern": "message:inbox:*",
        "result": [
            "message:inbox:from-alice/project-update:a1b2c3",
            "message:inbox:from-bob/question-about-memory:d4e5f6", 
            "message:inbox:from-system/daily-summary:g7h8i9"
        ],
        "decision": "Bob has a question about memory - that's relevant to my current focus. I'll prioritize that."
    })
    
    # Working: Find related content
    agent_thoughts.append({
        "time": "working",
        "thought": "Bob asked about memory. Let me find all my memory-related knowledge.",
        "action": "Find by semantic pattern",
        "patterns": [
            "knowledge:*:*memory*",
            "file:personal:notes/*memory*",
            "file:personal:learning/*memory*"
        ],
        "benefit": "I can search across different memory types and locations using semantic patterns!"
    })
    
    # Creating new memory with intelligent categorization
    agent_thoughts.append({
        "time": "learning",
        "thought": "I've learned something new about memory systems. Let me save this properly.",
        "action": "Create memory with auto-categorization",
        "content": "Discovered that semantic memory IDs help agents reason about content without loading it...",
        "auto_category": "learning/memory-systems/semantic-ids",
        "result": "file:personal:learning/memory-systems/semantic-ids:j1k2l3",
        "benefit": "The system helped me categorize this in a way I can find it later!"
    })
    
    # Finding related work
    agent_thoughts.append({
        "time": "connecting",
        "thought": "I wonder what else I've written about semantic systems.",
        "action": "Find related memories",
        "base": "file:personal:learning/memory-systems/semantic-ids:j1k2l3",
        "found": [
            "file:personal:learning/memory-systems/unified-approach:m4n5o6",
            "file:personal:ideas/semantic-understanding:p7q8r9",
            "message:outbox:to-alice/semantic-memory-proposal:s1t2u3"
        ],
        "insight": "I can see I've been building up ideas about this and even proposed it to Alice!"
    })
    
    return agent_thoughts


# Show the benefits in a structured way
def demonstrate_benefits():
    """Demonstrate the key benefits of the unified system."""
    
    benefits = {
        "semantic_understanding": {
            "old": "Agent sees: msg:/home/agent/inbox/message-12345.json",
            "new": "Agent sees: message:inbox:from-alice/project-update:a1b2c3",
            "benefit": "Instant understanding of sender and topic"
        },
        "pattern_matching": {
            "old": "Must search by text content only",
            "new": "Can search by semantic patterns like 'file:personal:projects/*'",
            "benefit": "Find related memories by meaning, not just text"
        },
        "relationship_discovery": {
            "old": "No way to find related memories",
            "new": "Can find memories related by topic, sender, type, etc.",
            "benefit": "Build knowledge graphs naturally"
        },
        "content_deduplication": {
            "old": "Same content can exist multiple times",
            "new": "Content hash in ID helps identify duplicates",
            "benefit": "Avoid redundant storage and processing"
        },
        "location_independence": {
            "old": "IDs break when files move",
            "new": "Semantic IDs remain stable",
            "benefit": "Robust references that survive reorganization"
        }
    }
    
    return benefits


if __name__ == "__main__":
    print("=== Agent Memory Usage Examples ===\n")
    
    # Show old vs new comparison
    print("OLD SYSTEM PROBLEMS:")
    for example in AGENT_MEMORY_EXAMPLES["old_system"]["examples"]:
        if "scenario" in example:
            print(f"\nScenario: {example['scenario']}")
            if "agent_thinks" in example:
                print(f"Agent thinks: {example['agent_thinks']}")
            if "problem" in example:
                print(f"Problem: {example['problem']}")
    
    print("\n\nNEW SYSTEM BENEFITS:")
    for example in AGENT_MEMORY_EXAMPLES["new_system"]["examples"]:
        print(f"\nScenario: {example['scenario']}")
        if "agent_thinks" in example:
            print(f"Agent thinks: {example['agent_thinks']}")
        print(f"Benefit: {example['benefit']}")
    
    print("\n\n=== Agent Daily Workflow ===")
    workflow = agent_daily_workflow_example()
    for step in workflow:
        print(f"\n[{step['time']}] {step['thought']}")
        if "benefit" in step:
            print(f"→ Benefit: {step['benefit']}")
        if "insight" in step:
            print(f"→ Insight: {step['insight']}")
    
    print("\n\n=== Key Benefits Summary ===")
    benefits = demonstrate_benefits()
    for benefit_type, details in benefits.items():
        print(f"\n{benefit_type.replace('_', ' ').title()}:")
        print(f"  Old: {details['old']}")
        print(f"  New: {details['new']}")
        print(f"  ✓ {details['benefit']}")