# Architecture & Design Review

Review guide for SOLID principles, design patterns, microservices, and clean architecture.

## Table of Contents
1. [SOLID Principles](#solid-principles)
2. [Design Patterns](#design-patterns)
3. [Clean Architecture](#clean-architecture)
4. [Microservices](#microservices)
5. [API Design](#api-design)
6. [Database Design](#database-design)
7. [Event-Driven Architecture](#event-driven-architecture)

---

## SOLID Principles

### Single Responsibility Principle (SRP)

A class should have only one reason to change.

```python
# BAD - Multiple responsibilities
class UserService:
    def create_user(self, data): ...
    def send_welcome_email(self, user): ...  # Email responsibility
    def generate_report(self, users): ...     # Reporting responsibility

# GOOD - Separated concerns
class UserService:
    def create_user(self, data): ...

class EmailService:
    def send_welcome_email(self, user): ...

class ReportService:
    def generate_user_report(self, users): ...
```

**Review Checklist:**
- [ ] Each class has a single, clear purpose
- [ ] Method names align with class responsibility
- [ ] No "and" in class descriptions (e.g., "handles users AND emails")

### Open/Closed Principle (OCP)

Open for extension, closed for modification.

```python
# BAD - Requires modification for new types
def calculate_area(shape):
    if shape.type == "circle":
        return 3.14 * shape.radius ** 2
    elif shape.type == "rectangle":
        return shape.width * shape.height
    # Must modify to add new shapes

# GOOD - Extensible without modification
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...

class Circle(Shape):
    def __init__(self, radius): self.radius = radius
    def area(self): return 3.14 * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, w, h): self.width, self.height = w, h
    def area(self): return self.width * self.height
```

**Review Checklist:**
- [ ] New features added through extension, not modification
- [ ] Switch statements on types indicate OCP violation
- [ ] Plugin/strategy patterns used for variation

### Liskov Substitution Principle (LSP)

Subtypes must be substitutable for their base types.

```python
# BAD - Breaks LSP
class Bird:
    def fly(self): return "Flying"

class Penguin(Bird):
    def fly(self): raise Exception("Can't fly!")  # Violates LSP

# GOOD - Proper hierarchy
class Bird:
    def move(self): ...

class FlyingBird(Bird):
    def fly(self): return "Flying"
    def move(self): return self.fly()

class Penguin(Bird):
    def swim(self): return "Swimming"
    def move(self): return self.swim()
```

**Review Checklist:**
- [ ] Subclasses don't throw unexpected exceptions
- [ ] Subclasses don't have stricter preconditions
- [ ] Subclasses don't have weaker postconditions
- [ ] No empty/stub method implementations

### Interface Segregation Principle (ISP)

Clients shouldn't depend on interfaces they don't use.

```typescript
// BAD - Fat interface
interface Worker {
    work(): void;
    eat(): void;
    sleep(): void;
}

class Robot implements Worker {
    work() { /* ... */ }
    eat() { throw new Error("Robots don't eat"); }  // Forced implementation
    sleep() { throw new Error("Robots don't sleep"); }
}

// GOOD - Segregated interfaces
interface Workable { work(): void; }
interface Eatable { eat(): void; }
interface Sleepable { sleep(): void; }

class Robot implements Workable {
    work() { /* ... */ }
}

class Human implements Workable, Eatable, Sleepable {
    work() { /* ... */ }
    eat() { /* ... */ }
    sleep() { /* ... */ }
}
```

**Review Checklist:**
- [ ] Interfaces are small and focused
- [ ] No empty method implementations to satisfy interface
- [ ] Classes implement only interfaces they need

### Dependency Inversion Principle (DIP)

Depend on abstractions, not concretions.

```python
# BAD - Depends on concrete implementation
class OrderService:
    def __init__(self):
        self.db = MySQLDatabase()  # Tight coupling

    def save_order(self, order):
        self.db.insert("orders", order)

# GOOD - Depends on abstraction
class OrderService:
    def __init__(self, repository: OrderRepository):  # Inject abstraction
        self.repository = repository

    def save_order(self, order):
        self.repository.save(order)

# Can inject any implementation
order_service = OrderService(MySQLOrderRepository())
order_service = OrderService(MongoOrderRepository())
order_service = OrderService(InMemoryOrderRepository())  # For testing
```

**Review Checklist:**
- [ ] High-level modules don't import low-level modules
- [ ] Dependencies injected, not instantiated
- [ ] Interfaces defined in the domain layer
- [ ] Easy to swap implementations (especially for testing)

---

## Design Patterns

### Creational Patterns

| Pattern | Use When | Red Flags |
|---------|----------|-----------|
| Factory | Object creation is complex | Too many if/switch in constructors |
| Builder | Many constructor parameters | Constructor with 5+ parameters |
| Singleton | Exactly one instance needed | Overused for convenience |

### Structural Patterns

| Pattern | Use When | Red Flags |
|---------|----------|-----------|
| Adapter | Incompatible interfaces | Wrapping everything unnecessarily |
| Decorator | Dynamic behavior addition | Deep nesting of decorators |
| Facade | Simplify complex subsystem | Facade doing too much |

### Behavioral Patterns

| Pattern | Use When | Red Flags |
|---------|----------|-----------|
| Strategy | Interchangeable algorithms | If/switch on algorithm type |
| Observer | Event notifications | Circular dependencies |
| Command | Undo/redo, queuing | Overengineering simple operations |

**Review Checklist:**
- [ ] Patterns used to solve actual problems, not prematurely
- [ ] Pattern implementation is correct
- [ ] Pattern improves, not complicates, the code

---

## Clean Architecture

### Layer Dependencies

```
┌─────────────────────────────────────┐
│         External Systems            │  Frameworks, UI, DB, APIs
├─────────────────────────────────────┤
│         Interface Adapters          │  Controllers, Presenters, Gateways
├─────────────────────────────────────┤
│         Application/Use Cases       │  Business logic orchestration
├─────────────────────────────────────┤
│         Domain/Entities             │  Core business rules
└─────────────────────────────────────┘

Dependencies point INWARD only (toward domain)
```

**Review Checklist:**
- [ ] Domain layer has no external dependencies
- [ ] Use cases orchestrate domain logic
- [ ] Infrastructure concerns at the edges
- [ ] No framework code in domain layer
- [ ] DTOs for crossing boundaries

### Domain-Driven Design (DDD)

| Concept | Purpose | Example |
|---------|---------|---------|
| Entity | Identity-based object | User, Order |
| Value Object | Immutable, no identity | Money, Address |
| Aggregate | Consistency boundary | Order + OrderItems |
| Repository | Collection abstraction | UserRepository |
| Service | Stateless operations | PaymentService |

---

## Microservices

### Service Boundaries

**Review Checklist:**
- [ ] Services aligned with business capabilities
- [ ] Each service owns its data
- [ ] No shared databases between services
- [ ] Loose coupling, high cohesion
- [ ] Independent deployability

### Communication Patterns

| Pattern | Use For | Considerations |
|---------|---------|----------------|
| Sync (REST/gRPC) | Simple queries, real-time | Cascading failures |
| Async (Events) | Decoupling, eventual consistency | Complexity |
| Saga | Distributed transactions | Compensation logic |

### Service Design Checklist

- [ ] API versioning strategy defined
- [ ] Circuit breakers for external calls
- [ ] Retry with exponential backoff
- [ ] Timeouts configured
- [ ] Health check endpoints
- [ ] Graceful degradation
- [ ] Idempotent operations where needed

### Anti-Patterns

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Distributed Monolith | Tight coupling across services | Proper boundaries |
| Chatty Services | Too many inter-service calls | Aggregate data, event-driven |
| Shared Database | Coupling through data | Database per service |
| Sync Call Chains | Cascading failures | Async, circuit breakers |

---

## API Design

### REST Best Practices

```
GET    /users          # List users
POST   /users          # Create user
GET    /users/{id}     # Get user
PUT    /users/{id}     # Replace user
PATCH  /users/{id}     # Update user
DELETE /users/{id}     # Delete user

GET    /users/{id}/orders  # Get user's orders (nested resource)
```

**Review Checklist:**
- [ ] Nouns for resources, verbs via HTTP methods
- [ ] Consistent naming (plural, kebab-case)
- [ ] Proper HTTP status codes
- [ ] HATEOAS for discoverability (optional)
- [ ] Pagination for lists
- [ ] Filtering, sorting, field selection
- [ ] Versioning (URL or header)

### Error Response Format

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Validation failed",
        "details": [
            {"field": "email", "message": "Invalid email format"}
        ]
    }
}
```

---

## Database Design

### Normalization Review

- [ ] No repeating groups (1NF)
- [ ] No partial dependencies (2NF)
- [ ] No transitive dependencies (3NF)
- [ ] Denormalization justified by performance needs

### Index Strategy

- [ ] Primary keys indexed
- [ ] Foreign keys indexed
- [ ] Query patterns analyzed
- [ ] Composite indexes in correct order
- [ ] No unused indexes

### Data Integrity

- [ ] Foreign key constraints
- [ ] Check constraints for valid values
- [ ] NOT NULL where required
- [ ] Unique constraints
- [ ] Soft delete vs hard delete strategy

---

## Event-Driven Architecture

### Event Design

```json
{
    "eventId": "uuid",
    "eventType": "OrderCreated",
    "timestamp": "ISO-8601",
    "source": "order-service",
    "data": { ... },
    "metadata": { "correlationId": "uuid", "userId": "uuid" }
}
```

**Review Checklist:**
- [ ] Events are immutable facts
- [ ] Events named in past tense (OrderCreated, not CreateOrder)
- [ ] Events contain all necessary data (no callbacks needed)
- [ ] Event schema versioning strategy
- [ ] Idempotent consumers
- [ ] Dead letter queue handling
- [ ] Event ordering guarantees where needed
