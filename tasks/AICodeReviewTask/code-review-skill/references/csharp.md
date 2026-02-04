# C# / .NET Code Review

C# and .NET specific best practices.

## Table of Contents
1. [Modern C# Features](#modern-c-features)
2. [LINQ Best Practices](#linq-best-practices)
3. [Async/Await](#asyncawait)
4. [Null Safety](#null-safety)
5. [Dependency Injection](#dependency-injection)
6. [Exception Handling](#exception-handling)
7. [Memory & Performance](#memory--performance)
8. [ASP.NET Core](#aspnet-core)

---

## Modern C# Features

### C# 10+ Features

```csharp
// File-scoped namespaces
namespace MyApp.Services;

// Global usings (in GlobalUsings.cs)
global using System.Collections.Generic;
global using Microsoft.Extensions.Logging;

// Record types for immutable data
public record User(int Id, string Name, string Email);

// Primary constructors (C# 12)
public class UserService(IUserRepository repository, ILogger<UserService> logger)
{
    public async Task<User?> GetUserAsync(int id)
    {
        logger.LogInformation("Getting user {Id}", id);
        return await repository.GetByIdAsync(id);
    }
}

// Collection expressions (C# 12)
int[] numbers = [1, 2, 3, 4, 5];
List<string> names = ["Alice", "Bob", "Charlie"];

// Pattern matching
string GetDiscount(Customer customer) => customer switch
{
    { IsPremium: true, Years: > 5 } => "30%",
    { IsPremium: true } => "20%",
    { Years: > 2 } => "10%",
    _ => "0%"
};
```

### Init-Only Properties

```csharp
// BAD - Mutable after construction
public class User
{
    public int Id { get; set; }
    public string Name { get; set; }
}

// GOOD - Immutable after construction
public class User
{
    public required int Id { get; init; }
    public required string Name { get; init; }
}

// Usage
var user = new User { Id = 1, Name = "Alice" };
// user.Id = 2; // Compile error
```

**Review Checklist:**
- [ ] Using modern C# features appropriately
- [ ] Records for DTOs and value objects
- [ ] `init` properties for immutability
- [ ] Pattern matching for complex conditionals
- [ ] File-scoped namespaces

---

## LINQ Best Practices

### Efficient Queries

```csharp
// BAD - Multiple enumerations
var users = GetUsers();
var count = users.Count();
var first = users.First();

// GOOD - Single enumeration
var users = GetUsers().ToList();
var count = users.Count;
var first = users[0];

// BAD - Loading everything then filtering
var allUsers = await context.Users.ToListAsync();
var activeUsers = allUsers.Where(u => u.IsActive);

// GOOD - Filter in database
var activeUsers = await context.Users
    .Where(u => u.IsActive)
    .ToListAsync();
```

### Query vs Method Syntax

```csharp
// Both are valid - be consistent
// Query syntax (better for joins)
var result = from u in users
             join o in orders on u.Id equals o.UserId
             where u.IsActive
             select new { u.Name, o.Total };

// Method syntax (more common)
var result = users
    .Where(u => u.IsActive)
    .Select(u => new { u.Name, u.Email });
```

### Avoid Common LINQ Pitfalls

```csharp
// BAD - Contains in loop (N+1)
foreach (var id in ids)
{
    if (users.Any(u => u.Id == id)) { }
}

// GOOD - HashSet lookup
var userIds = users.Select(u => u.Id).ToHashSet();
foreach (var id in ids)
{
    if (userIds.Contains(id)) { }
}
```

**Review Checklist:**
- [ ] No multiple enumeration of IEnumerable
- [ ] Filtering done at database level
- [ ] Using `Any()` instead of `Count() > 0`
- [ ] Using `FirstOrDefault()` with null check
- [ ] Projection (Select) to limit data loaded

---

## Async/Await

### Async Best Practices

```csharp
// BAD - Blocking on async
public User GetUser(int id)
{
    return GetUserAsync(id).Result; // Deadlock risk!
}

// GOOD - Async all the way
public async Task<User> GetUserAsync(int id)
{
    return await repository.GetByIdAsync(id);
}

// BAD - Async void (except event handlers)
public async void ProcessData()
{
    await Task.Delay(100);
}

// GOOD - Async Task
public async Task ProcessDataAsync()
{
    await Task.Delay(100);
}
```

### ConfigureAwait

```csharp
// In library code - use ConfigureAwait(false)
public async Task<Data> FetchDataAsync()
{
    var response = await httpClient.GetAsync(url).ConfigureAwait(false);
    return await response.Content.ReadAsAsync<Data>().ConfigureAwait(false);
}

// In ASP.NET Core - not needed (no sync context)
```

### Parallel Async

```csharp
// Sequential - slow
var user = await GetUserAsync(id);
var orders = await GetOrdersAsync(id);

// Parallel - fast
var userTask = GetUserAsync(id);
var ordersTask = GetOrdersAsync(id);
await Task.WhenAll(userTask, ordersTask);
var user = userTask.Result;
var orders = ordersTask.Result;
```

**Review Checklist:**
- [ ] Async all the way (no .Result or .Wait())
- [ ] No async void (except event handlers)
- [ ] Task.WhenAll for parallel operations
- [ ] CancellationToken passed through
- [ ] ConfigureAwait(false) in library code

---

## Null Safety

### Nullable Reference Types

```csharp
// Enable in csproj
<Nullable>enable</Nullable>

// Non-nullable by default
public class UserService
{
    private readonly ILogger _logger; // Cannot be null

    public User? FindUser(int id) // Can return null
    {
        return _repository.GetById(id);
    }

    public void ProcessUser(User user) // Cannot receive null
    {
        // Safe to use user without null check
    }
}
```

### Null Handling Patterns

```csharp
// Null-conditional operator
var name = user?.Profile?.Name;

// Null-coalescing operator
var displayName = user.Name ?? "Anonymous";

// Null-coalescing assignment
options.Timeout ??= TimeSpan.FromSeconds(30);

// Pattern matching null check
if (user is not null)
{
    // user is definitely not null here
}

// ArgumentNullException helper
ArgumentNullException.ThrowIfNull(user);
```

**Review Checklist:**
- [ ] Nullable reference types enabled
- [ ] Null checks at public API boundaries
- [ ] Using null-conditional operators
- [ ] No unnecessary null checks
- [ ] ArgumentNullException.ThrowIfNull for validation

---

## Dependency Injection

### Registration Patterns

```csharp
// Transient - new instance each time
services.AddTransient<IEmailService, EmailService>();

// Scoped - one per request (HTTP request in ASP.NET)
services.AddScoped<IUserRepository, UserRepository>();

// Singleton - one for application lifetime
services.AddSingleton<ICacheService, MemoryCacheService>();
```

### Avoid Service Locator

```csharp
// BAD - Service locator anti-pattern
public class UserService
{
    private readonly IServiceProvider _provider;

    public void Process()
    {
        var repo = _provider.GetRequiredService<IUserRepository>();
    }
}

// GOOD - Constructor injection
public class UserService
{
    private readonly IUserRepository _repository;

    public UserService(IUserRepository repository)
    {
        _repository = repository;
    }
}
```

**Review Checklist:**
- [ ] Constructor injection used
- [ ] Correct lifetime (Transient/Scoped/Singleton)
- [ ] No service locator pattern
- [ ] Interfaces for dependencies
- [ ] No captive dependencies (Singleton holding Scoped)

---

## Exception Handling

### Exception Patterns

```csharp
// Custom exceptions
public class NotFoundException : Exception
{
    public string ResourceType { get; }
    public string ResourceId { get; }

    public NotFoundException(string resourceType, string resourceId)
        : base($"{resourceType} with id {resourceId} was not found")
    {
        ResourceType = resourceType;
        ResourceId = resourceId;
    }
}

// Throwing with condition
public User GetUser(int id)
{
    return _repository.GetById(id)
        ?? throw new NotFoundException("User", id.ToString());
}
```

### Exception Filters

```csharp
try
{
    await ProcessAsync();
}
catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.NotFound)
{
    // Handle 404 specifically
}
catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.ServiceUnavailable)
{
    // Handle 503 specifically
}
```

**Review Checklist:**
- [ ] Specific exception types
- [ ] Exceptions have meaningful messages
- [ ] Using exception filters when appropriate
- [ ] Not catching Exception base class broadly
- [ ] Proper exception logging

---

## Memory & Performance

### Span and Memory

```csharp
// BAD - Allocates new string
string substring = text.Substring(0, 10);

// GOOD - No allocation
ReadOnlySpan<char> span = text.AsSpan(0, 10);

// Parsing without allocation
ReadOnlySpan<char> numberSpan = "12345".AsSpan();
int.TryParse(numberSpan, out var number);
```

### Avoid Boxing

```csharp
// BAD - Boxing value type
int value = 42;
object boxed = value; // Boxing occurs

// BAD - Boxing in collections
var list = new ArrayList();
list.Add(42); // Boxing

// GOOD - Generic collections
var list = new List<int>();
list.Add(42); // No boxing
```

### StringBuilder

```csharp
// BAD - String concatenation in loop
string result = "";
foreach (var item in items)
{
    result += item.ToString(); // Creates new string each iteration
}

// GOOD - StringBuilder
var sb = new StringBuilder();
foreach (var item in items)
{
    sb.Append(item);
}
var result = sb.ToString();
```

**Review Checklist:**
- [ ] Using Span<T> for slicing without allocation
- [ ] StringBuilder for string concatenation in loops
- [ ] Generic collections to avoid boxing
- [ ] Object pooling for frequently allocated objects
- [ ] Using struct where appropriate

---

## ASP.NET Core

### Controller Design

```csharp
[ApiController]
[Route("api/[controller]")]
public class UsersController : ControllerBase
{
    private readonly IUserService _userService;

    public UsersController(IUserService userService)
    {
        _userService = userService;
    }

    [HttpGet("{id}")]
    [ProducesResponseType(typeof(UserDto), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<UserDto>> GetUser(int id, CancellationToken cancellationToken)
    {
        var user = await _userService.GetByIdAsync(id, cancellationToken);
        if (user is null)
            return NotFound();

        return Ok(user);
    }
}
```

### Minimal APIs

```csharp
var app = builder.Build();

app.MapGet("/users/{id}", async (int id, IUserService service, CancellationToken ct) =>
{
    var user = await service.GetByIdAsync(id, ct);
    return user is null ? Results.NotFound() : Results.Ok(user);
});

app.MapPost("/users", async (CreateUserDto dto, IUserService service) =>
{
    var user = await service.CreateAsync(dto);
    return Results.Created($"/users/{user.Id}", user);
});
```

**Review Checklist:**
- [ ] CancellationToken passed to async methods
- [ ] Proper HTTP status codes
- [ ] Input validation (FluentValidation or Data Annotations)
- [ ] DTOs separate from domain models
- [ ] ProducesResponseType attributes for OpenAPI
