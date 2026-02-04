# Rust Code Review

Rust specific best practices and patterns.

## Table of Contents
1. [Ownership & Borrowing](#ownership--borrowing)
2. [Error Handling](#error-handling)
3. [Idiomatic Rust](#idiomatic-rust)
4. [Concurrency](#concurrency)
5. [Performance](#performance)
6. [Unsafe Code](#unsafe-code)
7. [Testing](#testing)

---

## Ownership & Borrowing

### Common Ownership Issues

```rust
// BAD - Unnecessary clone
fn process(data: Vec<String>) {
    let data = data.clone(); // Wasteful if data isn't needed after
    // ...
}

// GOOD - Take ownership or borrow as needed
fn process(data: Vec<String>) { // Takes ownership
    // ...
}

fn process(data: &[String]) { // Borrows
    // ...
}
```

### Borrowing Best Practices

```rust
// BAD - Borrowing when move is fine
fn get_name(user: &User) -> &str {
    &user.name
}

// Consider if User is no longer needed
fn into_name(user: User) -> String {
    user.name
}

// Use &str instead of &String for parameters
// BAD
fn greet(name: &String) { }

// GOOD
fn greet(name: &str) { }
```

### Lifetime Annotations

```rust
// When lifetimes are needed
struct Parser<'a> {
    input: &'a str,
}

impl<'a> Parser<'a> {
    fn new(input: &'a str) -> Self {
        Self { input }
    }

    fn parse(&self) -> &'a str {
        // Return reference with same lifetime as input
        self.input
    }
}

// Avoid lifetime when owned data works
struct OwnedParser {
    input: String,
}
```

**Review Checklist:**
- [ ] No unnecessary clones
- [ ] References used when ownership isn't needed
- [ ] &str preferred over &String for parameters
- [ ] Lifetimes only when necessary
- [ ] No dangling references

---

## Error Handling

### Result and Option

```rust
// BAD - Unwrap in library code
fn parse_config(path: &str) -> Config {
    let content = std::fs::read_to_string(path).unwrap();
    serde_json::from_str(&content).unwrap()
}

// GOOD - Propagate errors
fn parse_config(path: &str) -> Result<Config, ConfigError> {
    let content = std::fs::read_to_string(path)?;
    let config = serde_json::from_str(&content)?;
    Ok(config)
}

// Custom error type
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("Failed to read config file: {0}")]
    Io(#[from] std::io::Error),

    #[error("Failed to parse config: {0}")]
    Parse(#[from] serde_json::Error),
}
```

### Error Handling Patterns

```rust
// Use ? operator for propagation
fn process() -> Result<Output, Error> {
    let data = fetch_data()?;
    let parsed = parse(data)?;
    transform(parsed)
}

// Map errors with context
use anyhow::{Context, Result};

fn load_config() -> Result<Config> {
    let content = std::fs::read_to_string("config.toml")
        .context("Failed to read config file")?;

    toml::from_str(&content)
        .context("Failed to parse config file")
}

// Option handling
let value = map.get(&key)
    .ok_or_else(|| Error::NotFound(key.clone()))?;
```

**Review Checklist:**
- [ ] No unwrap() in library code
- [ ] Custom error types with thiserror
- [ ] anyhow for applications, thiserror for libraries
- [ ] Error context added with .context()
- [ ] ? operator used for propagation

---

## Idiomatic Rust

### Iterator Methods

```rust
// BAD - Manual iteration
let mut result = Vec::new();
for item in items {
    if item.is_valid() {
        result.push(item.value);
    }
}

// GOOD - Iterator chains
let result: Vec<_> = items
    .iter()
    .filter(|item| item.is_valid())
    .map(|item| item.value)
    .collect();

// Common patterns
let sum: i32 = numbers.iter().sum();
let any_valid = items.iter().any(|x| x.is_valid());
let all_valid = items.iter().all(|x| x.is_valid());
let found = items.iter().find(|x| x.id == target_id);
let count = items.iter().filter(|x| x.active).count();
```

### Pattern Matching

```rust
// Use pattern matching fully
match result {
    Ok(value) if value > 100 => handle_large(value),
    Ok(value) => handle_normal(value),
    Err(e) => handle_error(e),
}

// Destructure in matches
match user {
    User { name, age, .. } if age >= 18 => println!("{} is an adult", name),
    User { name, .. } => println!("{} is a minor", name),
}

// if let for single pattern
if let Some(value) = optional {
    process(value);
}

// let-else for early return (Rust 1.65+)
let Some(value) = optional else {
    return Err(Error::NotFound);
};
```

### Builder Pattern

```rust
#[derive(Default)]
pub struct RequestBuilder {
    url: Option<String>,
    method: Method,
    headers: HashMap<String, String>,
}

impl RequestBuilder {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn url(mut self, url: impl Into<String>) -> Self {
        self.url = Some(url.into());
        self
    }

    pub fn header(mut self, key: impl Into<String>, value: impl Into<String>) -> Self {
        self.headers.insert(key.into(), value.into());
        self
    }

    pub fn build(self) -> Result<Request, BuildError> {
        let url = self.url.ok_or(BuildError::MissingUrl)?;
        Ok(Request { url, method: self.method, headers: self.headers })
    }
}
```

**Review Checklist:**
- [ ] Iterator methods over manual loops
- [ ] Pattern matching used effectively
- [ ] if let for single-pattern matches
- [ ] let-else for early returns
- [ ] Builder pattern for complex construction

---

## Concurrency

### Thread Safety

```rust
// Arc for shared ownership across threads
use std::sync::Arc;

let data = Arc::new(vec![1, 2, 3]);
let data_clone = Arc::clone(&data);

std::thread::spawn(move || {
    println!("{:?}", data_clone);
});

// Mutex for interior mutability
use std::sync::Mutex;

let counter = Arc::new(Mutex::new(0));
let counter_clone = Arc::clone(&counter);

std::thread::spawn(move || {
    let mut num = counter_clone.lock().unwrap();
    *num += 1;
});

// RwLock for read-heavy workloads
use std::sync::RwLock;

let data = RwLock::new(HashMap::new());
// Multiple readers
let read_guard = data.read().unwrap();
// Exclusive writer
let mut write_guard = data.write().unwrap();
```

### Async Rust

```rust
// Use tokio or async-std
use tokio;

#[tokio::main]
async fn main() {
    let result = fetch_data().await;
}

// Concurrent execution
let (user, orders) = tokio::join!(
    fetch_user(id),
    fetch_orders(id)
);

// Select first to complete
tokio::select! {
    result = fetch_primary() => handle_primary(result),
    result = fetch_fallback() => handle_fallback(result),
}

// Spawn tasks
let handle = tokio::spawn(async {
    expensive_computation().await
});
let result = handle.await?;
```

**Review Checklist:**
- [ ] Send + Sync bounds satisfied for thread sharing
- [ ] Arc for shared ownership
- [ ] Mutex/RwLock for mutable shared state
- [ ] tokio::join! for concurrent async
- [ ] No blocking calls in async functions

---

## Performance

### Avoid Allocations

```rust
// BAD - Allocates on each call
fn get_greeting() -> String {
    "Hello".to_string()
}

// GOOD - Return &'static str when possible
fn get_greeting() -> &'static str {
    "Hello"
}

// Use Cow for optional allocation
use std::borrow::Cow;

fn process(input: &str) -> Cow<str> {
    if needs_modification(input) {
        Cow::Owned(modify(input))
    } else {
        Cow::Borrowed(input)
    }
}
```

### Efficient Collections

```rust
// Pre-allocate when size is known
let mut vec = Vec::with_capacity(1000);

// Use entry API for maps
use std::collections::HashMap;

let mut map: HashMap<String, i32> = HashMap::new();

// BAD - Double lookup
if !map.contains_key(&key) {
    map.insert(key.clone(), compute_value());
}

// GOOD - Single lookup
map.entry(key).or_insert_with(|| compute_value());
```

**Review Checklist:**
- [ ] Vec::with_capacity for known sizes
- [ ] Entry API for HashMap operations
- [ ] Cow for optional allocations
- [ ] &str over String where possible
- [ ] #[inline] used judiciously

---

## Unsafe Code

### When Unsafe is Acceptable

```rust
// Document safety invariants
/// # Safety
///
/// - `ptr` must be valid for reads
/// - `ptr` must be properly aligned
/// - The data at `ptr` must be initialized
unsafe fn read_value(ptr: *const i32) -> i32 {
    *ptr
}

// Minimize unsafe scope
fn process(data: &[u8]) -> Result<Value, Error> {
    // Safe code to validate input
    validate(data)?;

    // Minimal unsafe block
    let value = unsafe {
        // SAFETY: data has been validated above
        std::ptr::read_unaligned(data.as_ptr() as *const Value)
    };

    // Safe code to process result
    Ok(value)
}
```

**Review Checklist:**
- [ ] Unsafe blocks are minimal
- [ ] Safety invariants documented
- [ ] SAFETY comments explain why it's safe
- [ ] Consider safe alternatives first
- [ ] Unsafe abstracted behind safe API

---

## Testing

### Test Patterns

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_input() {
        let result = process("valid");
        assert_eq!(result, expected);
    }

    #[test]
    #[should_panic(expected = "invalid input")]
    fn test_invalid_input_panics() {
        process("invalid");
    }

    #[test]
    fn test_result_error() {
        let result = fallible_operation();
        assert!(result.is_err());
        assert!(matches!(result, Err(Error::NotFound)));
    }
}

// Async tests with tokio
#[tokio::test]
async fn test_async_function() {
    let result = async_operation().await;
    assert!(result.is_ok());
}

// Property-based testing with proptest
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_roundtrip(s in "\\PC*") {
        let encoded = encode(&s);
        let decoded = decode(&encoded)?;
        prop_assert_eq!(s, decoded);
    }
}
```

**Review Checklist:**
- [ ] Unit tests in same file with #[cfg(test)]
- [ ] Integration tests in tests/ directory
- [ ] #[should_panic] for expected panics
- [ ] Async tests with #[tokio::test]
- [ ] Property-based tests for invariants
