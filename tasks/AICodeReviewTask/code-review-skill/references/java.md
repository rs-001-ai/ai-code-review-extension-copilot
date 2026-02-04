# Java Code Review

Java specific best practices and patterns.

## Table of Contents
1. [Modern Java Features](#modern-java-features)
2. [Stream API](#stream-api)
3. [Null Safety](#null-safety)
4. [Concurrency](#concurrency)
5. [Exception Handling](#exception-handling)
6. [Spring Boot](#spring-boot)
7. [Testing](#testing)

---

## Modern Java Features

### Java 17+ Features

```java
// Records (Java 16+)
public record User(Long id, String name, String email) {}

// Pattern matching for instanceof (Java 16+)
if (obj instanceof String s) {
    System.out.println(s.length());
}

// Switch expressions (Java 14+)
String result = switch (status) {
    case ACTIVE -> "Active user";
    case INACTIVE -> "Inactive user";
    case PENDING -> "Pending approval";
    default -> "Unknown status";
};

// Text blocks (Java 15+)
String json = """
    {
        "name": "John",
        "age": 30
    }
    """;

// Sealed classes (Java 17+)
public sealed interface Shape permits Circle, Rectangle, Triangle {}
public final class Circle implements Shape {}
public final class Rectangle implements Shape {}
public non-sealed class Triangle implements Shape {}

// Pattern matching for switch (Java 21+)
String describe(Object obj) {
    return switch (obj) {
        case Integer i -> "Integer: " + i;
        case String s -> "String: " + s;
        case null -> "null";
        default -> "Unknown";
    };
}
```

### var Keyword

```java
// GOOD - Type is obvious
var users = new ArrayList<User>();
var name = user.getName();

// BAD - Type is not clear
var result = process(); // What type is result?
var x = getData(); // Unclear

// Cannot use with
// - Fields
// - Method parameters
// - Method return types
```

**Review Checklist:**
- [ ] Using modern Java features appropriately
- [ ] Records for immutable data carriers
- [ ] Switch expressions over switch statements
- [ ] var used only when type is obvious
- [ ] Pattern matching for instanceof checks

---

## Stream API

### Stream Best Practices

```java
// BAD - Stream reuse
var stream = list.stream().filter(x -> x.isActive());
var count = stream.count();
var first = stream.findFirst(); // IllegalStateException!

// GOOD - Create new stream
var count = list.stream().filter(x -> x.isActive()).count();
var first = list.stream().filter(x -> x.isActive()).findFirst();

// BAD - Nested streams (N+1)
users.stream()
    .map(user -> orderRepository.findByUserId(user.getId()))
    .toList();

// GOOD - Batch operation
var userIds = users.stream().map(User::getId).toList();
var orders = orderRepository.findByUserIds(userIds);
```

### Collector Patterns

```java
// Group by
Map<Status, List<User>> byStatus = users.stream()
    .collect(Collectors.groupingBy(User::getStatus));

// Partition (binary split)
Map<Boolean, List<User>> partitioned = users.stream()
    .collect(Collectors.partitioningBy(User::isActive));

// To map (watch for duplicates!)
Map<Long, User> byId = users.stream()
    .collect(Collectors.toMap(
        User::getId,
        Function.identity(),
        (existing, replacement) -> existing // Handle duplicates
    ));

// Custom collector
String joined = users.stream()
    .map(User::getName)
    .collect(Collectors.joining(", "));
```

**Review Checklist:**
- [ ] Streams not reused
- [ ] No blocking calls inside streams
- [ ] Parallel streams used judiciously
- [ ] Collectors.toMap handles duplicate keys
- [ ] Using method references where clear

---

## Null Safety

### Optional Usage

```java
// BAD - Optional as parameter
public void process(Optional<User> user) { }

// GOOD - Optional as return type
public Optional<User> findById(Long id) {
    return Optional.ofNullable(repository.get(id));
}

// BAD - get() without check
Optional<User> opt = findById(id);
User user = opt.get(); // NoSuchElementException risk

// GOOD - Safe extraction
User user = findById(id)
    .orElseThrow(() -> new NotFoundException("User not found"));

// GOOD - Default value
String name = user.getOptionalNickname()
    .orElse("Anonymous");

// GOOD - Chaining
String email = findById(id)
    .map(User::getEmail)
    .orElse("unknown@example.com");
```

### @Nullable Annotations

```java
import org.jetbrains.annotations.Nullable;
import org.jetbrains.annotations.NotNull;

public class UserService {
    @Nullable
    public User findById(Long id) {
        return repository.findById(id).orElse(null);
    }

    public void process(@NotNull User user) {
        Objects.requireNonNull(user, "User must not be null");
        // ...
    }
}
```

**Review Checklist:**
- [ ] Optional for return types, not parameters
- [ ] No Optional.get() without isPresent() or orElse
- [ ] @Nullable/@NotNull annotations on public APIs
- [ ] Objects.requireNonNull for validation
- [ ] Optional.empty() over null for optional returns

---

## Concurrency

### Thread Safety

```java
// BAD - Not thread-safe
private int counter = 0;
public void increment() {
    counter++; // Not atomic!
}

// GOOD - Atomic types
private final AtomicInteger counter = new AtomicInteger(0);
public void increment() {
    counter.incrementAndGet();
}

// GOOD - Synchronized (when needed)
private final Object lock = new Object();
public void process() {
    synchronized (lock) {
        // Critical section
    }
}
```

### Virtual Threads (Java 21+)

```java
// Traditional thread pool
ExecutorService executor = Executors.newFixedThreadPool(10);

// Virtual threads (Java 21+) - massive scalability
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    IntStream.range(0, 10_000).forEach(i -> {
        executor.submit(() -> {
            // Each task gets its own virtual thread
            return fetchData(i);
        });
    });
}
```

### CompletableFuture

```java
// Parallel execution
CompletableFuture<User> userFuture = CompletableFuture.supplyAsync(() ->
    userService.findById(id));
CompletableFuture<List<Order>> ordersFuture = CompletableFuture.supplyAsync(() ->
    orderService.findByUserId(id));

CompletableFuture.allOf(userFuture, ordersFuture).join();

User user = userFuture.get();
List<Order> orders = ordersFuture.get();

// Chaining
CompletableFuture<String> result = fetchUser(id)
    .thenApply(User::getName)
    .thenApply(String::toUpperCase)
    .exceptionally(ex -> "Unknown");
```

**Review Checklist:**
- [ ] Atomic types for shared counters
- [ ] Immutable objects preferred
- [ ] ConcurrentHashMap over synchronized HashMap
- [ ] Virtual threads for I/O-bound work (Java 21+)
- [ ] CompletableFuture for async composition

---

## Exception Handling

### Exception Best Practices

```java
// BAD - Catching Exception
try {
    process();
} catch (Exception e) {
    log.error("Error", e);
}

// GOOD - Specific exceptions
try {
    process();
} catch (IOException e) {
    log.error("IO error: {}", e.getMessage(), e);
    throw new ProcessingException("Failed to process", e);
}

// BAD - Swallowing exception
try {
    process();
} catch (Exception e) {
    // Silent failure
}

// GOOD - At least log
try {
    process();
} catch (Exception e) {
    log.error("Unexpected error", e);
    throw new RuntimeException("Processing failed", e);
}
```

### Try-with-resources

```java
// BAD - Manual resource management
InputStream is = new FileInputStream(file);
try {
    // use is
} finally {
    is.close(); // May throw, hiding original exception
}

// GOOD - Try-with-resources
try (var is = new FileInputStream(file)) {
    // use is
} // Automatically closed, suppressed exceptions handled
```

**Review Checklist:**
- [ ] Specific exception types caught
- [ ] Exception cause preserved
- [ ] Try-with-resources for AutoCloseable
- [ ] Meaningful exception messages
- [ ] Checked exceptions wrapped appropriately

---

## Spring Boot

### Controller Layer

```java
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping("/{id}")
    public ResponseEntity<UserDto> getUser(@PathVariable Long id) {
        return userService.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public UserDto createUser(@Valid @RequestBody CreateUserRequest request) {
        return userService.create(request);
    }
}
```

### Service Layer

```java
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    public Optional<User> findById(Long id) {
        return userRepository.findById(id);
    }

    @Transactional
    public User create(CreateUserRequest request) {
        var user = User.builder()
            .name(request.name())
            .email(request.email())
            .build();
        return userRepository.save(user);
    }
}
```

### Repository Layer

```java
public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByEmail(String email);

    @Query("SELECT u FROM User u WHERE u.status = :status")
    List<User> findByStatus(@Param("status") Status status);

    // Spring Data derived queries
    List<User> findByNameContainingIgnoreCase(String name);
}
```

**Review Checklist:**
- [ ] Constructor injection (not @Autowired on fields)
- [ ] @Transactional at service layer
- [ ] readOnly = true for read operations
- [ ] @Valid for input validation
- [ ] Proper HTTP status codes

---

## Testing

### JUnit 5 Patterns

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private UserService userService;

    @Test
    @DisplayName("should return user when found")
    void findById_whenExists_returnsUser() {
        // Arrange
        var user = new User(1L, "John", "john@example.com");
        when(userRepository.findById(1L)).thenReturn(Optional.of(user));

        // Act
        var result = userService.findById(1L);

        // Assert
        assertThat(result).isPresent();
        assertThat(result.get().getName()).isEqualTo("John");
    }

    @ParameterizedTest
    @ValueSource(strings = {"", " ", "  "})
    void create_withBlankName_throwsException(String name) {
        var request = new CreateUserRequest(name, "test@example.com");

        assertThatThrownBy(() -> userService.create(request))
            .isInstanceOf(ValidationException.class);
    }
}
```

### Integration Tests

```java
@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
class UserControllerIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");

    @Autowired
    private MockMvc mockMvc;

    @Test
    void createUser_withValidData_returns201() throws Exception {
        mockMvc.perform(post("/api/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "John", "email": "john@example.com"}
                    """))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name").value("John"));
    }
}
```

**Review Checklist:**
- [ ] Unit tests use mocks
- [ ] Integration tests use containers
- [ ] @DisplayName for readable test names
- [ ] Arrange-Act-Assert pattern
- [ ] Parameterized tests for multiple inputs
