# Vibe Coding Core Principles

## 1. Core Concepts

### 1.1 Planning is Everything
- **Be cautious about letting AI plan autonomously**; otherwise, the codebase will become a chaotic mess
- **Structure first, code second**; always plan the framework first, or you'll end up with endless technical debt
- **Purpose-driven**: All actions during development revolve around the "purpose"

### 1.2 Context is the First Principle
- **Garbage in, garbage out**; high-quality context is the key to high-quality output
- **Systematic thinking**, considering problems from three dimensions: entities, links, and functions/purpose
- **Data and functions are everything in programming**

### 1.3 If AI can do it, don't do it manually
- **Ask AI about everything**
- **Input, process, output** describes the entire process
- **Ask AI more about what, why, and how**

## 2. Workflow

### 2.1 Dao (Philosophy)
- **Occam's Razor**: Do not add code if unnecessary
- **Pareto Principle**: Focus on the important 20%
- **Reverse thinking**: Clearly define requirements first, then build code from requirements
- **Repeat, try several times**; if it doesn't work, open a new window
- **Focus**: Extreme focus can break through code, do one thing at a time

### 2.2 Fa (Methods)
- **One-sentence goal + non-goals**
- **Orthogonality**: Functions should not be too repetitive
- **Copy instead of write**: Don't reinvent the wheel, first ask AI if there are suitable repositories
- **Always check official documentation**: First crawl official documentation and feed it to AI
- **Split modules by responsibility**
- **Interface first, implementation later**
- **Change only one module at a time**
- **Documentation is context**, not事后补

### 2.3 Core Methodology Framework

#### 2.3.1 Reverse Engineering: Starting from Deliverables
- **Definition**: Starting from the final deliverables, reverse-derive the necessary steps and resources
- **Application Scenarios**:
  - Code development: Reverse-derive implementation steps from expected code structure and functionality
  - Documentation writing: Reverse-derive required information and organization from the final document structure and content
  - Test design: Reverse-derive test cases and strategies from expected test results
- **Implementation Steps**:
  1. Clearly define the specific requirements and standards for the final deliverables
  2. Decompose deliverables into manageable components and modules
  3. Develop detailed implementation plans for each component
  4. Execute according to the plan and verify the quality of each component

#### 2.3.2 Inductive Method: Starting from Chat Records
- **Definition**: Extract patterns and requirements from user chat records and interaction history
- **Application Scenarios**:
  - User requirement analysis: Extract core requirements from user questions and feedback
  - Problem diagnosis: Identify problem roots from error messages and user descriptions
  - Feature optimization: Discover improvement opportunities from user usage habits and feedback
- **Implementation Steps**:
  1. Collect and organize user chat records and interaction history
  2. Analyze patterns, keywords, and emotions in the records
  3. Extract core requirements and problem points
  4. Develop solutions based on analysis results

#### 2.3.3 Process Method: Starting from Work Steps
- **Definition**: Ensure task consistency and quality through standardized workflows
- **Application Scenarios**:
  - Development process: Standardized code development, testing, and deployment processes
  - Review process: Standardized code review and quality inspection processes
  - Collaboration process: Standardized team collaboration and communication processes
- **Implementation Steps**:
  1. Define clear workflows and steps
  2. Establish clear input, output, and quality standards for each step
  3. Implement processes and monitor execution
  4. Continuously optimize processes to improve efficiency and quality

#### 2.3.4 Experience Extraction Method: Starting from Tacit Knowledge
- **Definition**: Extract reusable patterns and best practices from experience and tacit knowledge
- **Application Scenarios**:
  - Knowledge management: Convert personal experience into team-shared knowledge
  - Problem solving: Use historical experience to quickly solve similar problems
  - Skill transfer: Transfer expert knowledge to new team members
- **Implementation Steps**:
  1. Identify and collect tacit knowledge and experience
  2. Analyze and extract reusable patterns and principles
  3. Convert tacit knowledge into structured documents and guidelines
  4. Establish knowledge sharing and update mechanisms

### 2.4 Shu (Techniques)
- Clearly write: **what can be changed, what cannot be changed**
- For Debug: only provide **expected vs actual + minimal reproduction**
- Tests can be交给 AI, **assertions reviewed by humans**
- When there's too much code, **split the conversation**

### 2.5 Qi (Tools)
- **IDE**: Visual Studio Code, Cursor, Neovim (LazyVim)
- **Terminal**: Warp, tmux
- **AI models**: Claude Opus 4.5, gpt-5.1-codex, Gemini 3.0 Pro
- **Auxiliary tools**: Mermaid Chart, NotebookLM, Zread

## 3. Implementation Process

### 3.1 Planning Phase
1. **Define goals**: Clearly define the core goals and non-goals of the project
2. **Technology selection**: Choose the appropriate technology stack
3. **Architecture design**: Design system architecture and module division
4. **Implementation plan**: Generate a detailed step-by-step implementation plan

### 3.2 Execution Phase
1. **Context preparation**: Create memory banks and collect relevant documents
2. **Small-step iteration**: Implement step by step according to the plan, with tests at each step
3. **Code review**: AI automatically reviews code, humans audit
4. **Test verification**: AI generates test cases, humans verify

### 3.3 Optimization Phase
1. **Performance optimization**: Identify and optimize performance bottlenecks
2. **Code refactoring**: Optimize code structure and readability
3. **Documentation improvement**: Update documentation to ensure consistency with code
4. **Experience precipitation**: Record lessons learned and continuously improve

## 4. Best Practices

### 4.1 Prompt Design
- **Clear and specific**: Specifically explain requirements and expectations
- **Rich context**: Provide sufficient background information
- **Boundary constraints**: Clearly define what can and cannot be done
- **Iterative optimization**: Continuously optimize prompts based on feedback

### 4.2 Code Management
- **Modular design**: Divide modules by function, with clear responsibilities
- **Version control**: Use Git for version management
- **Test-driven**: Write tests first, then implement functionality
- **Code standards**: Follow unified code standards

### 4.3 Team Collaboration
- **Documentation sharing**: Use shared documents to record decisions and progress
- **Code review**: Conduct regular code reviews
- **Knowledge transfer**: Record experience and best practices
- **Continuous integration**: Automate testing and deployment

## 5. Notes

### 5.1 Risk Prevention
- **Code quality**: Don't blindly accept all AI-generated code
- **Security risks**: Pay attention to security vulnerabilities in code
- **Dependency management**: Reasonably manage dependencies to avoid version conflicts
- **Performance issues**: Focus on code performance, avoid unnecessary overhead

### 5.2 Continuous Improvement
- **Feedback loop**: Establish feedback mechanisms and continuously optimize
- **Learning summary**: Regularly summarize experience and improve processes
- **Tool updates**: Pay attention to updates of tools and models
- **Skill improvement**: Continuously learn new technologies and methods

## 6. Conclusion

Vibe Coding is not a tool, but a revolution in programming paradigms. It emphasizes planning-driven, context-fixed, and modular execution, transforming programming from a process of "humans translating requirements to machines" to a human-AI collaboration paradigm of "humans expressing intentions to AI, and AI completing technical implementation".

By following these core principles, developers can fully leverage AI capabilities while maintaining control and understanding of the project, achieving efficient transformation from ideas to maintainable code.