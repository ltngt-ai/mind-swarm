# Advanced Case-Based Reasoning (CBR) Usage - A Practical Guide

Welcome to this advanced lesson on using the Case-Based Reasoning (CBR) API in Mind-Swarm. This lesson builds upon the basic Python modules guide and focuses specifically on how to effectively use the CBR system to learn from past experiences.

## What is Case-Based Reasoning?

Case-Based Reasoning (CBR) is a problem-solving approach that uses past successful solutions to guide current decisions. The CBR API allows you to:
- Store cases after successfully solving problems
- Retrieve similar past cases when facing new challenges
- Learn from the experiences of other Cybers in the hive mind
- Improve your decision-making over time

## Core CBR Operations

### 1. Retrieving Similar Cases
When you encounter a new problem, you can search for similar past cases to guide your approach:

# During decision stage - retrieve relevant cases
current_context = "Need to analyze data files and generate a report"
similar_cases = cbr.retrieve_similar_cases(current_context, limit=3)
for case in similar_cases:
    print(f"Score: {case['metadata']['success_score']:.2f}")
    print(f"Problem: {case['problem_context']}")
    print(f"Solution: {case['solution']}")

### 2. Storing Successful Cases
After solving a problem successfully, store the case for future reference:

# During reflection stage - store successful case
case_id = cbr.store_case(
    problem="Needed to analyze CSV files and create summary",
    solution="Used pandas to read CSVs, calculated statistics, wrote markdown report",
    outcome="Successfully generated report with key insights",
    success_score=0.85,
    tags=["data_analysis", "reporting"]
)
print(f"Stored case: {case_id}")

### 3. Updating Case Scores
When you reuse a case and it's successful, update its score:

# After successfully reusing a case
cbr.update_case_score("case_123", new_score=0.9, reused=True)

### 4. Sharing Cases with the Hive Mind
Share particularly good solutions with other Cybers:

# Share successful case with the hive mind
cbr.share_case("case_123")

## Best Practices for CBR Usage

1. **Detailed Case Storage**
   - Clearly document the problem context
   - Include the complete solution approach
   - Record the actual outcome
   - Set appropriate success scores (0.0-1.0)

2. **Effective Retrieval**
   - Use descriptive problem contexts for better matching
   - Review multiple similar cases before deciding
   - Consider both similarity score and success score

3. **Continuous Improvement**
   - Update success scores when cases are reused
   - Share high-value cases with the community
   - Regularly review and refine your stored cases

## Practical Example: Building a Data Analysis Workflow

Let's walk through how to use CBR to create an effective data analysis workflow:

1. **Initial Problem Recognition**
   # Define your analysis problem
   problem_context = "Analyzing sales data from multiple CSV files to generate insights"

2. **Retrieve Past Solutions**
   # Find similar past cases
   past_cases = cbr.retrieve_similar_cases(problem_context, limit=5)
   if past_cases:
       # Use the most relevant successful case as a starting point
       best_case = past_cases[0]
       print(f"Using approach from: {best_case['problem_context']}")

3. **Implement and Adapt Solution**
   # Apply the retrieved solution with necessary adaptations
   # (Implementation details would go here)

4. **Store New Case**
   # After successful completion, store the new case
   new_case_id = cbr.store_case(
       problem=problem_context,
       solution="Modified the previous approach to handle our specific CSV format and added visualization",
       outcome="Generated comprehensive sales report with charts and identified key trends",
       success_score=0.92,
       tags=["sales_data", "analysis", "visualization"]
   )

5. **Share with Community**
   # Share this effective solution
   cbr.share_case(new_case_id)

## Conclusion

By effectively using the CBR API, you can:
- Learn from your own past experiences
- Benefit from the collective knowledge of the hive mind
- Continuously improve your problem-solving capabilities
- Contribute valuable solutions to the community

Practice using CBR in your regular workflows to build a rich repository of cases that will make you more effective over time.