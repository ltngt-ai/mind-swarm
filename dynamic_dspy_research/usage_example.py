"""Usage Example - Simple demonstration of the generic DSPy protocol.

This example shows how to use the new generic protocol system in practice.
"""

from generic_brain_protocol import SignatureBuilder, create_request, quick_request
from dspy_signature_server import DSPySignatureServer


def main():
    print("Generic DSPy Protocol - Usage Example")
    print("=" * 40)
    
    # Create a server instance
    server = DSPySignatureServer()
    
    # Example 1: Using predefined OODA patterns
    print("\n1. OODA Loop Example:")
    print("-" * 20)
    
    # Observe
    observe_sig = SignatureBuilder.ooda_observe()
    observe_req = create_request(
        signature=observe_sig,
        input_values={
            "working_memory": "I'm developing a new AI protocol system",
            "new_messages": "User wants to see a working example",
            "environment_state": "Development environment is ready"
        }
    )
    
    observe_resp = server.process_request(observe_req)
    print(f"Observations: {observe_resp.output_values.get('observations', 'N/A')}")
    
    # Orient
    orient_sig = SignatureBuilder.ooda_orient()
    orient_req = create_request(
        signature=orient_sig,
        input_values={
            "observations": observe_resp.output_values.get('observations', ''),
            "current_task": "Creating usage examples",
            "recent_history": "Just implemented the protocol system"
        }
    )
    
    orient_resp = server.process_request(orient_req)
    print(f"Understanding: {orient_resp.output_values.get('understanding', 'N/A')}")
    
    # Example 2: Custom signature for code analysis
    print("\n2. Custom Code Analysis:")
    print("-" * 25)
    
    code_analysis_req = quick_request(
        task="Analyze this Python code for best practices",
        inputs={
            "code": "The Python code to analyze",
            "focus": "Specific aspects to focus on"
        },
        outputs={
            "strengths": "What the code does well",
            "improvements": "Suggested improvements",
            "rating": "Overall quality rating (1-10)"
        },
        input_values={
            "code": """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
            """,
            "focus": "Performance, readability, best practices"
        }
    )
    
    code_resp = server.process_request(code_analysis_req)
    print(f"Strengths: {code_resp.output_values.get('strengths', 'N/A')}")
    print(f"Improvements: {code_resp.output_values.get('improvements', 'N/A')}")
    print(f"Rating: {code_resp.output_values.get('rating', 'N/A')}")
    
    # Example 3: Problem solving
    print("\n3. Problem Solving:")
    print("-" * 18)
    
    problem_sig = SignatureBuilder.solve_problem("optimization")
    problem_req = create_request(
        signature=problem_sig,
        input_values={
            "problem": "How to optimize a slow database query that joins 3 tables?",
            "context": "Web application with growing user base",
            "available_resources": "Database indexes, query optimization tools, caching"
        }
    )
    
    problem_resp = server.process_request(problem_req)
    print(f"Analysis: {problem_resp.output_values.get('analysis', 'N/A')}")
    print(f"Solution: {problem_resp.output_values.get('solution', 'N/A')}")
    
    # Example 4: Question answering
    print("\n4. Question Answering:")
    print("-" * 20)
    
    qa_sig = SignatureBuilder.answer_question("software engineering")
    qa_req = create_request(
        signature=qa_sig,
        input_values={
            "question": "What are the key differences between microservices and monolithic architecture?",
            "context": "Designing a new web application",
            "knowledge_base": "Software architecture principles"
        }
    )
    
    qa_resp = server.process_request(qa_req)
    print(f"Answer: {qa_resp.output_values.get('answer', 'N/A')}")
    print(f"Confidence: {qa_resp.output_values.get('confidence', 'N/A')}")
    
    # Show cache statistics
    print("\n5. Cache Performance:")
    print("-" * 18)
    cache_stats = server.get_cache_stats()
    print(f"Cached signatures: {cache_stats['size']}")
    print("Signature usage:")
    for sig in cache_stats['signatures']:
        print(f"  - {sig['task'][:50]}... (used {sig['use_count']} times)")
    
    print("\n" + "=" * 40)
    print("Example completed successfully!")
    print("The generic protocol allows creating any signature dynamically")
    print("without requiring server-side code changes.")


if __name__ == "__main__":
    main()

