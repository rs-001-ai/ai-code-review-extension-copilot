# Go Code Review

Go specific best practices and patterns.

## Table of Contents
1. [Code Style](#code-style)
2. [Error Handling](#error-handling)
3. [Concurrency](#concurrency)
4. [Interfaces](#interfaces)
5. [Testing](#testing)
6. [Performance](#performance)
7. [Common Pitfalls](#common-pitfalls)

---

## Code Style

### Naming Conventions

```go
// Package names: lowercase, single word
package user

// Exported (public): PascalCase
type UserService struct {}
func (s *UserService) GetUser(id int) {}

// Unexported (private): camelCase
type userRepository struct {}
func (r *userRepository) findById(id int) {}

// Acronyms: all caps
type HTTPClient struct {}
type JSONParser struct {}
var userID int // not userId

// Interfaces: -er suffix for single method
type Reader interface { Read(p []byte) (n int, err error) }
type Writer interface { Write(p []byte) (n int, err error) }
```

### Formatting

```go
// gofmt handles formatting - run it always

// Imports grouped: stdlib, external, internal
import (
    "context"
    "fmt"

    "github.com/gin-gonic/gin"
    "go.uber.org/zap"

    "myproject/internal/user"
)

// Short variable declaration in functions
func process() {
    user := getUser() // Preferred
    var user User     // When zero value is meaningful
}
```

**Review Checklist:**
- [ ] Code formatted with gofmt/goimports
- [ ] Naming follows conventions
- [ ] Imports properly grouped
- [ ] No exported names from main package
- [ ] Package names match directory names

---

## Error Handling

### Error Patterns

```go
// BAD - Ignoring errors
data, _ := json.Marshal(user)

// GOOD - Handle or propagate
data, err := json.Marshal(user)
if err != nil {
    return fmt.Errorf("marshal user: %w", err)
}

// BAD - Generic error
if user == nil {
    return errors.New("error")
}

// GOOD - Descriptive error
if user == nil {
    return fmt.Errorf("user %d not found", id)
}
```

### Error Wrapping (Go 1.13+)

```go
// Wrap with context using %w
func GetUser(id int) (*User, error) {
    user, err := repo.FindByID(id)
    if err != nil {
        return nil, fmt.Errorf("get user %d: %w", id, err)
    }
    return user, nil
}

// Check wrapped errors
if errors.Is(err, ErrNotFound) {
    // Handle not found
}

// Extract specific error type
var validErr *ValidationError
if errors.As(err, &validErr) {
    // Handle validation error
}
```

### Custom Errors

```go
// Sentinel errors for known conditions
var (
    ErrNotFound     = errors.New("not found")
    ErrUnauthorized = errors.New("unauthorized")
)

// Structured errors for more context
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation failed on %s: %s", e.Field, e.Message)
}
```

**Review Checklist:**
- [ ] No ignored errors (no `_, err = ...`)
- [ ] Errors wrapped with context
- [ ] Using errors.Is/As for checking
- [ ] Descriptive error messages
- [ ] Sentinel errors for known conditions

---

## Concurrency

### Goroutines

```go
// BAD - Goroutine leak
func process() {
    go func() {
        for {
            doWork() // Runs forever with no way to stop
        }
    }()
}

// GOOD - Use context for cancellation
func process(ctx context.Context) {
    go func() {
        for {
            select {
            case <-ctx.Done():
                return
            default:
                doWork()
            }
        }
    }()
}
```

### Channels

```go
// Channel direction in function signatures
func producer(out chan<- int) { // Send only
    out <- 42
}

func consumer(in <-chan int) { // Receive only
    value := <-in
}

// Buffered vs unbuffered
ch := make(chan int)    // Unbuffered - blocks until received
ch := make(chan int, 10) // Buffered - blocks when full

// Close channels from sender
func produce(ch chan<- int) {
    defer close(ch)
    for i := 0; i < 10; i++ {
        ch <- i
    }
}

// Range over channel
for value := range ch {
    process(value)
}
```

### Sync Primitives

```go
// WaitGroup for coordinating goroutines
var wg sync.WaitGroup

for _, item := range items {
    wg.Add(1)
    go func(item Item) {
        defer wg.Done()
        process(item)
    }(item) // Pass item to avoid closure capture issue
}

wg.Wait()

// Mutex for shared state
type Counter struct {
    mu    sync.Mutex
    value int
}

func (c *Counter) Increment() {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.value++
}

// Once for initialization
var (
    instance *Singleton
    once     sync.Once
)

func GetInstance() *Singleton {
    once.Do(func() {
        instance = &Singleton{}
    })
    return instance
}
```

**Review Checklist:**
- [ ] Goroutines have exit conditions
- [ ] Context used for cancellation
- [ ] Channels closed by sender
- [ ] WaitGroup for goroutine coordination
- [ ] Mutex protects shared state
- [ ] No goroutine leaks

---

## Interfaces

### Interface Design

```go
// BAD - Large interface
type UserService interface {
    Create(user *User) error
    Update(user *User) error
    Delete(id int) error
    GetByID(id int) (*User, error)
    GetByEmail(email string) (*User, error)
    List() ([]*User, error)
    // ... many more methods
}

// GOOD - Small, focused interfaces
type UserCreator interface {
    Create(user *User) error
}

type UserFinder interface {
    GetByID(id int) (*User, error)
    GetByEmail(email string) (*User, error)
}

// Accept interfaces, return structs
func NewHandler(finder UserFinder) *Handler {
    return &Handler{finder: finder}
}
```

### Interface Location

```go
// Define interfaces where they're used (consumer), not where implemented

// In handler package (consumer)
type UserFinder interface {
    GetByID(id int) (*User, error)
}

type Handler struct {
    users UserFinder
}

// In service package (implementer) - no interface needed
type UserService struct {}

func (s *UserService) GetByID(id int) (*User, error) {
    // Implementation
}
```

**Review Checklist:**
- [ ] Small, focused interfaces
- [ ] Interfaces defined by consumer
- [ ] Accept interfaces, return structs
- [ ] No empty interface{} when avoidable (use any)
- [ ] Interface satisfaction checked at compile time

---

## Testing

### Test Structure

```go
func TestUserService_GetByID(t *testing.T) {
    // Arrange
    repo := &mockRepo{
        users: map[int]*User{1: {ID: 1, Name: "Alice"}},
    }
    service := NewUserService(repo)

    // Act
    user, err := service.GetByID(1)

    // Assert
    if err != nil {
        t.Fatalf("unexpected error: %v", err)
    }
    if user.Name != "Alice" {
        t.Errorf("expected name Alice, got %s", user.Name)
    }
}

// Table-driven tests
func TestValidateEmail(t *testing.T) {
    tests := []struct {
        name    string
        email   string
        wantErr bool
    }{
        {"valid email", "test@example.com", false},
        {"missing @", "testexample.com", true},
        {"empty", "", true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := ValidateEmail(tt.email)
            if (err != nil) != tt.wantErr {
                t.Errorf("ValidateEmail(%q) error = %v, wantErr %v",
                    tt.email, err, tt.wantErr)
            }
        })
    }
}
```

### Mocking

```go
// Interface-based mocking
type mockRepo struct {
    users map[int]*User
    err   error
}

func (m *mockRepo) GetByID(id int) (*User, error) {
    if m.err != nil {
        return nil, m.err
    }
    return m.users[id], nil
}

// Testing error conditions
func TestUserService_GetByID_Error(t *testing.T) {
    repo := &mockRepo{err: errors.New("db error")}
    service := NewUserService(repo)

    _, err := service.GetByID(1)

    if err == nil {
        t.Error("expected error, got nil")
    }
}
```

**Review Checklist:**
- [ ] Table-driven tests for multiple cases
- [ ] t.Run for subtests
- [ ] Mocks via interfaces
- [ ] Error cases tested
- [ ] t.Parallel() for independent tests

---

## Performance

### Preallocate Slices

```go
// BAD - Grows dynamically
var result []int
for _, item := range items {
    result = append(result, item.Value)
}

// GOOD - Preallocate
result := make([]int, 0, len(items))
for _, item := range items {
    result = append(result, item.Value)
}

// Or direct assignment
result := make([]int, len(items))
for i, item := range items {
    result[i] = item.Value
}
```

### String Building

```go
// BAD - String concatenation in loop
var result string
for _, s := range items {
    result += s // Allocates new string each time
}

// GOOD - strings.Builder
var builder strings.Builder
for _, s := range items {
    builder.WriteString(s)
}
result := builder.String()
```

### Avoid Copies

```go
// BAD - Copies large struct
func process(data LargeStruct) {}

// GOOD - Pass pointer
func process(data *LargeStruct) {}

// For slices, passing is already efficient (it's a header)
func process(data []int) {} // Fine - doesn't copy elements
```

**Review Checklist:**
- [ ] Slices preallocated when size known
- [ ] strings.Builder for string concatenation
- [ ] Pointers for large structs
- [ ] sync.Pool for frequently allocated objects
- [ ] Avoid allocations in hot paths

---

## Common Pitfalls

### Loop Variable Capture

```go
// BAD (before Go 1.22) - All goroutines see last value
for _, item := range items {
    go func() {
        process(item) // Bug: captures loop variable
    }()
}

// GOOD - Pass as argument (always works)
for _, item := range items {
    go func(item Item) {
        process(item)
    }(item)
}

// Go 1.22+ - Loop variables are per-iteration (fixed)
for _, item := range items {
    go func() {
        process(item) // Safe in Go 1.22+
    }()
}
```

### Nil Slices vs Empty Slices

```go
var s []int        // nil slice
s := []int{}       // empty slice
s := make([]int, 0) // empty slice

// All have len=0, cap=0
// nil slice marshals to null in JSON
// empty slice marshals to [] in JSON

// Check for empty
if len(s) == 0 { } // Works for both nil and empty
```

### Defer in Loops

```go
// BAD - Defers accumulate until function returns
for _, file := range files {
    f, _ := os.Open(file)
    defer f.Close() // Not closed until function ends
}

// GOOD - Use closure or explicit close
for _, file := range files {
    func() {
        f, _ := os.Open(file)
        defer f.Close()
        // process f
    }()
}
```

**Review Checklist:**
- [ ] Loop variable captured correctly
- [ ] Defer not accumulating in loops
- [ ] Nil vs empty slice considered
- [ ] Map concurrent access protected
- [ ] Context passed through call chain
