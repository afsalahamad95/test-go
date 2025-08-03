# Step 1: Import necessary modules
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence  # Fixed import for RunnableSequence
# Step 2: Initialize the Ollama LLM
llm = OllamaLLM(model="llama3.2", base_url="https://afsals-macbook-pro.tailf5cb33.ts.net/ http://localhost:11434")  # Using llama3.2 model
# Step 3: Define the Go code review prompt template
go_review_prompt = PromptTemplate(
    input_variables=["code"],  # The variable that will hold the actual code
    template="""
You are a senior Golang engineer. Review the following Go code and provide structured feedback.
Focus on:
- Bugs or logical errors
- Concurrency and goroutine issues
- Performance optimizations
- Idiomatic Go style and naming
- Potential security risks
- Dead code and bugs
- Industry standards ensuring long term compliance and maintainability
- Logging and error handling
- Unit test coverage
- Sensitive information and secrets exposure
- Function headers and comments for readability
- Spelling and grammar
IMPORTANT: First identify issues by line number, then provide a code suggestion that GitHub users can commit directly.
For each issue:
1. Identify the issue using line numbers.
2. Provide a brief explanation of the problem, following the structure given in the image.  Include spelling/grammar issues.
3. Follow immediately with a GitHub suggestion block like this:
```suggestion
Replacement code here
```

Example format:
Line 42: This code has a race condition because it accesses a shared variable without locks.
```suggestion
mutex.Lock()
sharedVar += 1
mutex.Unlock()
```

The ```suggestion 
Replacement code here

Go code:
```go
{code}
```
""")

# Step 4: Create the review chain
review_chain = RunnableSequence(
    go_review_prompt | llm
)

# Step 5: Function to review Go code
def review_go_code(code_snippet):
    result = review_chain.invoke({"code": code_snippet})
    return result

# Example usage
if __name__ == "__main__":
    # Example Go code to review
    example_code = """
    package main
    
    import "fmt"
    
    func main() {
        ch := make(chan int)
        go func() {
            ch <- 42
        }()
        fmt.Println(<-ch)
    }
    """
    
    review = review_go_code(example_code)
    print("Code Review:")
    print(review)