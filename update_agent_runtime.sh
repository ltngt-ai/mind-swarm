#!/bin/bash
# Update runtime code for all agents

SUBSPACE_ROOT="${SUBSPACE_ROOT:-subspace}"

echo "Updating runtime for general agents..."
for agent_dir in "$SUBSPACE_ROOT"/agents/*/; do
    if [ -d "$agent_dir" ]; then
        agent_name=$(basename "$agent_dir")
        
        # Check if it's an IO agent
        if [[ -f "$agent_dir/runtime/base_code/io_mind.py" ]]; then
            echo "Updating IO agent: $agent_name"
            cp -r subspace/runtime/io_agent_template/* "$agent_dir/runtime/base_code/"
        else
            echo "Updating general agent: $agent_name"
            cp -r subspace/runtime/base_code_template/* "$agent_dir/runtime/base_code/"
        fi
    fi
done

echo "Runtime update complete!"