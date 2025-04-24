# Step 1: Import necessary modules
from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence  # Fixed import for RunnableSequence
# Step 2: Initialize the Ollama LLM
llm = OllamaLLM(model="llama3.2")  # Using llama3.2 model
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
- Make sure code does not exceed 120 characters per line
- config values should not be accessed anywhere other than main.go
- no unused constants should be in code
- function headers are mandatory

IMPORTANT: For each specific issue you find, mention the line number using this format:
"Line X: [Your feedback about this specific line]"

If an issue spans multiple lines, use:
"Lines X-Y: [Your feedback about these lines]"

Give actionable feedback. Be concise and technical. 
Give actionable feedback in bullet points. Be concise and technical.
Go code:
```go
{code}
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