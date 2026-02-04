# C/C++ Code Review

C and C++ specific best practices and patterns.

## Table of Contents
1. [Modern C++ Features](#modern-c-features)
2. [Memory Management](#memory-management)
3. [RAII and Resource Management](#raii-and-resource-management)
4. [Error Handling](#error-handling)
5. [Concurrency](#concurrency)
6. [Performance](#performance)
7. [C-Specific Guidelines](#c-specific-guidelines)
8. [Security](#security)

---

## Modern C++ Features

### C++17/20 Features

```cpp
// Structured bindings (C++17)
auto [name, age] = get_person();
for (const auto& [key, value] : map) { }

// std::optional (C++17)
std::optional<User> find_user(int id) {
    if (auto it = users.find(id); it != users.end()) {
        return it->second;
    }
    return std::nullopt;
}

// if constexpr (C++17)
template<typename T>
auto process(T value) {
    if constexpr (std::is_integral_v<T>) {
        return value * 2;
    } else {
        return value;
    }
}

// std::string_view (C++17)
void process(std::string_view sv) { } // No allocation

// Concepts (C++20)
template<typename T>
concept Printable = requires(T t) {
    { std::cout << t } -> std::same_as<std::ostream&>;
};

template<Printable T>
void print(const T& value) {
    std::cout << value;
}

// Ranges (C++20)
auto result = numbers
    | std::views::filter([](int n) { return n % 2 == 0; })
    | std::views::transform([](int n) { return n * 2; });
```

### auto and Type Deduction

```cpp
// GOOD - Type is obvious
auto ptr = std::make_unique<Widget>();
auto it = container.begin();
auto lambda = [](int x) { return x * 2; };

// BAD - Type is unclear
auto result = process(); // What type?
auto x = foo.bar().baz(); // Unclear

// Use trailing return type for complex deduction
auto get_value() -> std::optional<int> {
    // ...
}
```

**Review Checklist:**
- [ ] Using modern C++ features appropriately
- [ ] auto used when type is clear
- [ ] std::optional for nullable values
- [ ] std::string_view for non-owning strings
- [ ] Concepts for template constraints

---

## Memory Management

### Smart Pointers

```cpp
// GOOD - Unique ownership
std::unique_ptr<Widget> widget = std::make_unique<Widget>();

// GOOD - Shared ownership (when truly needed)
std::shared_ptr<Resource> resource = std::make_shared<Resource>();

// BAD - Raw new/delete
Widget* widget = new Widget();
delete widget;

// BAD - Array with new[]
int* arr = new int[100];
delete[] arr;

// GOOD - Use containers
std::vector<int> arr(100);
```

### When to Use Which Pointer

| Type | Use Case |
|------|----------|
| `unique_ptr` | Single ownership, factory returns |
| `shared_ptr` | Shared ownership (rare) |
| `weak_ptr` | Non-owning reference to shared_ptr |
| Raw pointer | Non-owning reference, observer |
| Reference | Non-null, non-owning reference |

### Memory Issues to Watch

```cpp
// BAD - Dangling reference
const std::string& get_name() {
    std::string name = "test";
    return name; // Dangling!
}

// BAD - Use after free
auto* ptr = obj.get();
obj.reset();
ptr->method(); // Use after free!

// BAD - Double free
auto* raw = unique_ptr.release();
delete raw;
// unique_ptr destructor may also delete

// BAD - Memory leak with exceptions
void process() {
    auto* data = new Data();
    may_throw(); // Leak if throws
    delete data;
}

// GOOD - RAII handles exceptions
void process() {
    auto data = std::make_unique<Data>();
    may_throw(); // Automatically cleaned up
}
```

**Review Checklist:**
- [ ] No raw new/delete
- [ ] make_unique/make_shared used
- [ ] No dangling pointers/references
- [ ] Clear ownership semantics
- [ ] No use-after-free

---

## RAII and Resource Management

### RAII Pattern

```cpp
// GOOD - Resource managed by constructor/destructor
class FileHandle {
public:
    explicit FileHandle(const char* path)
        : handle_(fopen(path, "r")) {
        if (!handle_) throw std::runtime_error("Failed to open file");
    }

    ~FileHandle() {
        if (handle_) fclose(handle_);
    }

    // Delete copy, allow move
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;
    FileHandle(FileHandle&& other) noexcept : handle_(other.handle_) {
        other.handle_ = nullptr;
    }
    FileHandle& operator=(FileHandle&& other) noexcept {
        if (this != &other) {
            if (handle_) fclose(handle_);
            handle_ = other.handle_;
            other.handle_ = nullptr;
        }
        return *this;
    }

private:
    FILE* handle_;
};
```

### Rule of Zero/Five

```cpp
// Rule of Zero - Prefer this
// If you don't manage resources, don't define special members
class Person {
    std::string name;
    int age;
    // Compiler-generated constructors are fine
};

// Rule of Five - When managing resources
// Define all five or none: destructor, copy ctor, copy assign, move ctor, move assign
class Resource {
public:
    ~Resource();
    Resource(const Resource&);
    Resource& operator=(const Resource&);
    Resource(Resource&&) noexcept;
    Resource& operator=(Resource&&) noexcept;
};
```

**Review Checklist:**
- [ ] RAII for all resources
- [ ] Rule of Zero preferred
- [ ] Rule of Five if needed
- [ ] noexcept on move operations
- [ ] Explicit on single-arg constructors

---

## Error Handling

### Exception vs Error Codes

```cpp
// Exceptions for exceptional cases
void process_file(const std::string& path) {
    std::ifstream file(path);
    if (!file) {
        throw std::runtime_error("Failed to open: " + path);
    }
}

// std::expected (C++23) or similar for expected errors
std::expected<User, Error> find_user(int id) {
    if (auto it = users.find(id); it != users.end()) {
        return it->second;
    }
    return std::unexpected(Error::NotFound);
}

// noexcept specification
void swap(Widget& a, Widget& b) noexcept {
    // Must not throw
}
```

### Exception Safety Guarantees

| Level | Guarantee |
|-------|-----------|
| No-throw | Operation never throws |
| Strong | On exception, state unchanged |
| Basic | On exception, no leaks, valid state |
| None | Undefined behavior possible |

```cpp
// Strong guarantee with copy-and-swap
Widget& operator=(Widget other) noexcept {  // Copy made first
    swap(*this, other);  // noexcept swap
    return *this;
}  // other destructor cleans up old data
```

**Review Checklist:**
- [ ] Exception safety level documented
- [ ] noexcept where guaranteed
- [ ] RAII ensures basic guarantee
- [ ] No resource leaks on exception
- [ ] Error handling strategy consistent

---

## Concurrency

### Thread Safety

```cpp
// std::mutex for mutual exclusion
class Counter {
public:
    void increment() {
        std::lock_guard<std::mutex> lock(mutex_);
        ++count_;
    }

    int get() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return count_;
    }

private:
    mutable std::mutex mutex_;
    int count_ = 0;
};

// std::shared_mutex for readers-writer lock
class Cache {
public:
    std::optional<Value> get(const Key& key) const {
        std::shared_lock lock(mutex_);  // Multiple readers OK
        auto it = data_.find(key);
        return it != data_.end() ? std::optional(it->second) : std::nullopt;
    }

    void put(const Key& key, Value value) {
        std::unique_lock lock(mutex_);  // Exclusive write
        data_[key] = std::move(value);
    }

private:
    mutable std::shared_mutex mutex_;
    std::unordered_map<Key, Value> data_;
};
```

### Atomic Operations

```cpp
// Atomic for lock-free operations
std::atomic<int> counter{0};
counter.fetch_add(1, std::memory_order_relaxed);

// Atomic flag for spinlocks (rarely needed)
std::atomic_flag flag = ATOMIC_FLAG_INIT;

// Memory ordering (default is sequentially consistent)
// Use relaxed only when you understand implications
```

### Async Patterns

```cpp
// std::async for simple async tasks
auto future = std::async(std::launch::async, [] {
    return expensive_computation();
});
auto result = future.get();

// std::thread with RAII wrapper (jthread C++20)
std::jthread worker([](std::stop_token token) {
    while (!token.stop_requested()) {
        do_work();
    }
});
// Automatically joins on destruction
```

**Review Checklist:**
- [ ] Shared data protected by mutex
- [ ] lock_guard/unique_lock/shared_lock used
- [ ] No data races
- [ ] Deadlock potential analyzed
- [ ] Atomics used correctly

---

## Performance

### Move Semantics

```cpp
// Enable move semantics
class Widget {
public:
    Widget(Widget&& other) noexcept
        : data_(std::move(other.data_)) {
        other.data_ = nullptr;
    }
};

// Move when you're done with a value
std::vector<Widget> widgets;
widgets.push_back(std::move(local_widget));

// Return by value (move or copy elision)
std::vector<int> create_data() {
    std::vector<int> result;
    // ... populate
    return result;  // Moved or elided, never copied
}
```

### Avoid Copies

```cpp
// BAD - Unnecessary copy
void process(std::string s) { }

// GOOD - Const reference for read
void process(const std::string& s) { }

// GOOD - string_view for non-owning
void process(std::string_view sv) { }

// GOOD - Perfect forwarding
template<typename T>
void wrapper(T&& arg) {
    actual(std::forward<T>(arg));
}
```

### Reserve Capacity

```cpp
// BAD - Multiple reallocations
std::vector<int> v;
for (int i = 0; i < 10000; ++i) {
    v.push_back(i);
}

// GOOD - Reserve upfront
std::vector<int> v;
v.reserve(10000);
for (int i = 0; i < 10000; ++i) {
    v.push_back(i);
}
```

**Review Checklist:**
- [ ] Move semantics enabled
- [ ] Const references for read-only
- [ ] Reserve for known sizes
- [ ] Avoid unnecessary copies
- [ ] emplace_back over push_back

---

## C-Specific Guidelines

### Memory Management in C

```c
// Always check malloc return
void* ptr = malloc(size);
if (ptr == NULL) {
    // Handle allocation failure
}

// Match malloc/free, calloc/free
int* arr = calloc(n, sizeof(int));
// ... use arr
free(arr);
arr = NULL;  // Prevent use-after-free

// Avoid buffer overflows
char buffer[100];
strncpy(buffer, source, sizeof(buffer) - 1);
buffer[sizeof(buffer) - 1] = '\0';

// Use snprintf, not sprintf
snprintf(buffer, sizeof(buffer), "Value: %d", value);
```

### Safe String Handling

```c
// BAD - Buffer overflow
char dest[10];
strcpy(dest, user_input);  // Unsafe!

// GOOD - Bounded copy
char dest[10];
strncpy(dest, user_input, sizeof(dest) - 1);
dest[sizeof(dest) - 1] = '\0';

// Even better - strlcpy if available
strlcpy(dest, user_input, sizeof(dest));
```

**Review Checklist:**
- [ ] malloc return checked
- [ ] free matches alloc type
- [ ] No buffer overflows
- [ ] Bounded string functions used
- [ ] Pointers set to NULL after free

---

## Security

### Common Vulnerabilities

```cpp
// Buffer overflow
// BAD
void process(char* input) {
    char buffer[256];
    strcpy(buffer, input);  // Overflow if input > 255
}

// GOOD
void process(const char* input) {
    std::string buffer(input);  // Safe
}

// Integer overflow
// BAD
size_t total = count * element_size;  // May overflow
void* ptr = malloc(total);

// GOOD
if (count > SIZE_MAX / element_size) {
    // Handle overflow
}
size_t total = count * element_size;

// Format string vulnerability
// BAD
printf(user_input);  // Can read/write memory!

// GOOD
printf("%s", user_input);
```

### Input Validation

```cpp
// Validate array indices
if (index >= 0 && static_cast<size_t>(index) < array.size()) {
    // Safe to access
}

// Use at() for bounds checking (throws on invalid)
auto value = container.at(index);

// Validate pointers before use
if (ptr != nullptr) {
    ptr->method();
}
```

**Review Checklist:**
- [ ] No buffer overflows
- [ ] Integer overflow checked
- [ ] Format strings not from user input
- [ ] Array bounds validated
- [ ] Pointers validated before use
