# JavaScript/TypeScript Code Review

JavaScript and TypeScript specific best practices.

## Table of Contents
1. [TypeScript Best Practices](#typescript-best-practices)
2. [Modern JavaScript](#modern-javascript)
3. [Async Patterns](#async-patterns)
4. [Error Handling](#error-handling)
5. [Common Pitfalls](#common-pitfalls)
6. [Testing](#testing)
7. [Node.js Specifics](#nodejs-specifics)
8. [Bun Specifics](#bun-specifics)

---

## TypeScript Best Practices

### Type Safety

```typescript
// BAD - any type
function process(data: any): any {
    return data.value;
}

// GOOD - Proper typing
function process<T extends { value: unknown }>(data: T): T['value'] {
    return data.value;
}
```

```typescript
// BAD - Type assertion abuse
const user = response.data as User;

// GOOD - Type guard
function isUser(data: unknown): data is User {
    return (
        typeof data === 'object' &&
        data !== null &&
        'id' in data &&
        'name' in data
    );
}

if (isUser(response.data)) {
    // data is typed as User here
}
```

### Strict Configuration

```json
// tsconfig.json
{
    "compilerOptions": {
        "strict": true,
        "noUncheckedIndexedAccess": true,
        "noImplicitReturns": true,
        "noFallthroughCasesInSwitch": true,
        "exactOptionalPropertyTypes": true
    }
}
```

### Utility Types

```typescript
// Use built-in utility types
type UserUpdate = Partial<User>;
type RequiredUser = Required<User>;
type UserPreview = Pick<User, 'id' | 'name'>;
type UserWithoutPassword = Omit<User, 'password'>;
type ReadonlyUser = Readonly<User>;
type UserRecord = Record<string, User>;

// Discriminated unions for state
type AsyncState<T> =
    | { status: 'idle' }
    | { status: 'loading' }
    | { status: 'success'; data: T }
    | { status: 'error'; error: Error };
```

**Review Checklist:**
- [ ] Strict mode enabled
- [ ] No `any` types (use `unknown` if needed)
- [ ] Type guards instead of assertions
- [ ] Utility types used appropriately
- [ ] Discriminated unions for complex state
- [ ] Generic constraints properly defined

---

## Modern JavaScript

### ES2020+ Features

```javascript
// Optional chaining
const name = user?.profile?.name;

// Nullish coalescing
const value = input ?? defaultValue;

// Logical assignment
options.timeout ??= 5000;
options.retries ||= 3;

// Object shorthand
const { name, age } = user;
const newUser = { name, age, ...defaults };

// Array methods
const found = items.find(x => x.id === id);
const filtered = items.filter(x => x.active);
const mapped = items.map(x => x.name);
const hasActive = items.some(x => x.active);
const allActive = items.every(x => x.active);
const flattened = nested.flat();
const unique = [...new Set(items)];
```

### Destructuring & Spread

```javascript
// BAD - Manual property access
function createUser(options) {
    const name = options.name;
    const email = options.email;
    const role = options.role || 'user';
}

// GOOD - Destructuring with defaults
function createUser({ name, email, role = 'user' }) {
    // Direct access to name, email, role
}

// Clone and merge objects
const updated = { ...original, ...changes };

// Clone arrays
const copy = [...original];
```

**Review Checklist:**
- [ ] Using modern syntax (ES2020+)
- [ ] Optional chaining for safe access
- [ ] Nullish coalescing instead of `||` for defaults
- [ ] Destructuring for cleaner code
- [ ] Array methods instead of manual loops

---

## Async Patterns

### Promise Best Practices

```javascript
// BAD - Mixing callbacks and promises
function fetchData(callback) {
    fetch(url)
        .then(res => callback(null, res))
        .catch(err => callback(err));
}

// GOOD - Pure promises/async-await
async function fetchData() {
    const response = await fetch(url);
    return response.json();
}
```

```javascript
// BAD - Sequential when parallel possible
async function loadAll() {
    const users = await fetchUsers();
    const orders = await fetchOrders();
    return { users, orders };
}

// GOOD - Parallel execution
async function loadAll() {
    const [users, orders] = await Promise.all([
        fetchUsers(),
        fetchOrders()
    ]);
    return { users, orders };
}
```

### Promise Patterns

```javascript
// Promise.allSettled - Don't fail fast
const results = await Promise.allSettled([
    fetch(url1),
    fetch(url2),
    fetch(url3)
]);

const successful = results
    .filter(r => r.status === 'fulfilled')
    .map(r => r.value);

// Race with timeout
async function fetchWithTimeout(url, timeout = 5000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, { signal: controller.signal });
        return response;
    } finally {
        clearTimeout(timeoutId);
    }
}
```

**Review Checklist:**
- [ ] async/await over raw promises
- [ ] Promise.all for parallel operations
- [ ] Promise.allSettled when partial failure is OK
- [ ] Proper timeout handling
- [ ] AbortController for cancellation

---

## Error Handling

### Error Types

```typescript
// Define custom error types
class ValidationError extends Error {
    constructor(public field: string, message: string) {
        super(message);
        this.name = 'ValidationError';
    }
}

class NotFoundError extends Error {
    constructor(resource: string, id: string) {
        super(`${resource} with id ${id} not found`);
        this.name = 'NotFoundError';
    }
}
```

### Error Handling Patterns

```typescript
// Result type pattern
type Result<T, E = Error> =
    | { ok: true; value: T }
    | { ok: false; error: E };

function parseJson<T>(json: string): Result<T> {
    try {
        return { ok: true, value: JSON.parse(json) };
    } catch (e) {
        return { ok: false, error: e as Error };
    }
}

// Usage
const result = parseJson<User>(input);
if (result.ok) {
    console.log(result.value);
} else {
    console.error(result.error);
}
```

**Review Checklist:**
- [ ] Custom error classes for different scenarios
- [ ] Errors caught at appropriate boundaries
- [ ] Error context preserved (cause)
- [ ] No swallowing errors silently
- [ ] Async errors properly caught

---

## Common Pitfalls

### Equality Checks

```javascript
// BAD - Loose equality
if (value == null) { }
if (value == 0) { }

// GOOD - Strict equality
if (value === null || value === undefined) { }
if (value === 0) { }

// GOOD - Nullish check
if (value == null) { } // Only OK for null/undefined check
```

### This Binding

```javascript
// BAD - Lost this binding
class Handler {
    value = 42;

    handle() {
        console.log(this.value);
    }
}

button.addEventListener('click', handler.handle); // this is undefined

// GOOD - Arrow function or bind
class Handler {
    value = 42;

    handle = () => {
        console.log(this.value); // this is preserved
    }
}
```

### Array/Object References

```javascript
// BAD - Mutating state
function addItem(items, item) {
    items.push(item); // Mutates original
    return items;
}

// GOOD - Return new array
function addItem(items, item) {
    return [...items, item];
}

// GOOD - Immutable update
const newState = {
    ...state,
    user: { ...state.user, name: 'New Name' }
};
```

**Review Checklist:**
- [ ] Strict equality (===) used
- [ ] this binding handled correctly
- [ ] Immutable updates for state
- [ ] No unintended mutations
- [ ] Proper null/undefined handling

---

## Testing

### Jest Patterns

```typescript
// Describe blocks for organization
describe('UserService', () => {
    describe('createUser', () => {
        it('should create user with valid data', async () => {
            const user = await userService.createUser(validData);
            expect(user.id).toBeDefined();
            expect(user.email).toBe(validData.email);
        });

        it('should throw on invalid email', async () => {
            await expect(
                userService.createUser({ ...validData, email: 'invalid' })
            ).rejects.toThrow(ValidationError);
        });
    });
});

// Mocking
jest.mock('./database');
const mockDb = jest.mocked(database);

beforeEach(() => {
    jest.clearAllMocks();
});
```

### Vitest Patterns

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Similar to Jest but with vi instead of jest
vi.mock('./database');

describe('Service', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });
});
```

**Review Checklist:**
- [ ] Tests organized in describe blocks
- [ ] Happy path and error cases covered
- [ ] Mocks cleared between tests
- [ ] Async tests properly awaited
- [ ] No test interdependencies

---

## Node.js Specifics

### Environment & Config

```typescript
// BAD - Direct env access scattered
const port = process.env.PORT;

// GOOD - Centralized config with validation
import { z } from 'zod';

const envSchema = z.object({
    PORT: z.coerce.number().default(3000),
    DATABASE_URL: z.string().url(),
    NODE_ENV: z.enum(['development', 'production', 'test']),
});

export const config = envSchema.parse(process.env);
```

### Graceful Shutdown

```typescript
async function shutdown() {
    console.log('Shutting down...');
    await server.close();
    await db.disconnect();
    process.exit(0);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
```

**Review Checklist:**
- [ ] Environment variables validated at startup
- [ ] Graceful shutdown handlers
- [ ] Unhandled rejection handlers
- [ ] Proper error logging
- [ ] Security headers configured

---

## Bun Specifics

### Bun Built-ins

```typescript
// File I/O (faster than Node.js fs)
const file = Bun.file('./data.json');
const data = await file.json();
await Bun.write('./output.txt', 'content');

// SQLite built-in
import { Database } from 'bun:sqlite';
const db = new Database('mydb.sqlite');
const users = db.query('SELECT * FROM users').all();

// Built-in test runner
import { test, expect } from 'bun:test';
test('example', () => {
    expect(1 + 1).toBe(2);
});

// Hashing
const hash = Bun.hash('data');
const password = await Bun.password.hash('secret');
const valid = await Bun.password.verify('secret', password);
```

**Review Checklist:**
- [ ] Using Bun built-ins where applicable
- [ ] Bun.file for file operations
- [ ] bun:sqlite for SQLite
- [ ] Bun.password for secure hashing
