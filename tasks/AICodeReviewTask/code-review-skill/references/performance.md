# Performance Review Checklist

Guide for reviewing code performance across all layers.

## Table of Contents
1. [Algorithm Complexity](#algorithm-complexity)
2. [Database Performance](#database-performance)
3. [Memory Management](#memory-management)
4. [Concurrency](#concurrency)
5. [Caching](#caching)
6. [Network & I/O](#network--io)
7. [Frontend Performance](#frontend-performance)

---

## Algorithm Complexity

### Time Complexity Review

| Complexity | Acceptable For | Watch For |
|------------|----------------|-----------|
| O(1) | Any operation | - |
| O(log n) | Search, tree ops | - |
| O(n) | Single pass | Nested in loops |
| O(n log n) | Sorting | Unnecessary sorts |
| O(n²) | Small datasets only | Large n, nested loops |
| O(n³+) | Avoid if possible | Almost always bad |

### Common Performance Issues

```python
# BAD - O(n²) when O(n) is possible
def has_duplicates(items):
    for i, item in enumerate(items):
        if item in items[i+1:]:  # O(n) lookup each time
            return True
    return False

# GOOD - O(n) with set
def has_duplicates(items):
    return len(items) != len(set(items))
```

```python
# BAD - O(n) lookup in list repeatedly
users_list = [...]
for user_id in user_ids:
    user = next((u for u in users_list if u.id == user_id), None)  # O(n)

# GOOD - O(1) lookup with dict
users_by_id = {u.id: u for u in users_list}
for user_id in user_ids:
    user = users_by_id.get(user_id)  # O(1)
```

**Review Checklist:**
- [ ] No unnecessary nested loops over large collections
- [ ] Appropriate data structures (set for membership, dict for lookup)
- [ ] Sorting only when necessary
- [ ] Early exits when possible

---

## Database Performance

### Query Optimization

```sql
-- BAD - SELECT *
SELECT * FROM orders WHERE user_id = 123;

-- GOOD - Select only needed columns
SELECT id, status, total FROM orders WHERE user_id = 123;
```

```sql
-- BAD - N+1 query pattern
for user in users:
    orders = db.query("SELECT * FROM orders WHERE user_id = ?", user.id)

-- GOOD - Single query with JOIN or IN
SELECT * FROM orders WHERE user_id IN (1, 2, 3, ...);
```

### Index Usage

```sql
-- Ensure indexes exist for:
-- 1. WHERE clause columns
-- 2. JOIN columns
-- 3. ORDER BY columns
-- 4. Frequently filtered columns

-- Check query plan
EXPLAIN ANALYZE SELECT ...;
```

### Common Database Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| N+1 Queries | Many small queries | Eager loading, JOINs |
| Missing Index | Full table scans | Add appropriate index |
| Over-fetching | SELECT * | Select specific columns |
| Large Result Sets | Memory issues | Pagination, streaming |
| Lock Contention | Deadlocks, slow writes | Shorter transactions |

**Review Checklist:**
- [ ] No N+1 query patterns
- [ ] Indexes on frequently queried columns
- [ ] No SELECT * in production code
- [ ] Pagination for list queries
- [ ] Connection pooling configured
- [ ] Transactions kept short
- [ ] Explain plans checked for complex queries

---

## Memory Management

### Memory Leaks

```python
# BAD - Growing cache without limits
cache = {}
def get_data(key):
    if key not in cache:
        cache[key] = expensive_fetch(key)  # Never evicted
    return cache[key]

# GOOD - LRU cache with max size
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_data(key):
    return expensive_fetch(key)
```

```javascript
// BAD - Event listener leak
class Component {
    mount() {
        window.addEventListener('resize', this.handleResize);
    }
    // Missing cleanup!
}

// GOOD - Clean up listeners
class Component {
    mount() {
        window.addEventListener('resize', this.handleResize);
    }
    unmount() {
        window.removeEventListener('resize', this.handleResize);
    }
}
```

### Large Data Processing

```python
# BAD - Load entire file into memory
with open('large_file.csv') as f:
    data = f.readlines()  # All in memory
    for line in data:
        process(line)

# GOOD - Stream processing
with open('large_file.csv') as f:
    for line in f:  # One line at a time
        process(line)

# GOOD - Generator for transformations
def process_file(filename):
    with open(filename) as f:
        for line in f:
            yield transform(line)
```

**Review Checklist:**
- [ ] Caches have size limits and eviction
- [ ] Event listeners cleaned up
- [ ] Large files processed in streams
- [ ] Generators used for lazy evaluation
- [ ] No circular references holding objects
- [ ] Resources closed/disposed properly

---

## Concurrency

### Thread Safety

```python
# BAD - Race condition
counter = 0
def increment():
    global counter
    counter += 1  # Not atomic!

# GOOD - Thread-safe counter
from threading import Lock
counter = 0
lock = Lock()

def increment():
    global counter
    with lock:
        counter += 1
```

### Async/Await Best Practices

```python
# BAD - Sequential async calls
async def get_user_data(user_id):
    user = await get_user(user_id)
    orders = await get_orders(user_id)  # Waits for user first
    return user, orders

# GOOD - Parallel async calls
async def get_user_data(user_id):
    user, orders = await asyncio.gather(
        get_user(user_id),
        get_orders(user_id)
    )
    return user, orders
```

### Connection Pool Sizing

```
Pool Size = (CPU cores * 2) + effective_spindle_count

For most web apps: 10-20 connections per service instance
```

**Review Checklist:**
- [ ] Shared mutable state protected
- [ ] Async calls parallelized when independent
- [ ] Connection pools properly sized
- [ ] No blocking calls in async code
- [ ] Deadlock potential analyzed
- [ ] Thread pool sizes appropriate

---

## Caching

### Cache Strategy

| Strategy | Use When | Trade-off |
|----------|----------|-----------|
| Cache-Aside | Read-heavy, can tolerate stale | Application manages cache |
| Write-Through | Strong consistency needed | Higher write latency |
| Write-Behind | Write-heavy | Potential data loss |
| Read-Through | Simplify application code | Cache becomes critical path |

### Cache Invalidation

```python
# Key patterns for cache invalidation
# 1. TTL-based expiration
cache.set(key, value, ttl=300)

# 2. Event-based invalidation
def update_user(user_id, data):
    db.update(user_id, data)
    cache.delete(f"user:{user_id}")

# 3. Version-based keys
cache_key = f"user:{user_id}:v{version}"
```

**Review Checklist:**
- [ ] Cache keys are unique and meaningful
- [ ] TTL configured appropriately
- [ ] Cache invalidation strategy defined
- [ ] Cache stampede prevention (locking, early expiration)
- [ ] Cache hit rate monitored
- [ ] Fallback when cache unavailable

---

## Network & I/O

### HTTP Optimization

```python
# BAD - Sequential HTTP calls
def get_all_data():
    result1 = requests.get(url1)
    result2 = requests.get(url2)
    result3 = requests.get(url3)

# GOOD - Parallel with connection reuse
import aiohttp

async def get_all_data():
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            session.get(url1),
            session.get(url2),
            session.get(url3)
        )
```

### Connection Management

- [ ] HTTP keep-alive enabled
- [ ] Connection pooling for databases
- [ ] Timeouts configured (connect, read, total)
- [ ] Retry with exponential backoff
- [ ] Circuit breaker for failing services

### Payload Optimization

- [ ] Response compression (gzip, brotli)
- [ ] Pagination for large lists
- [ ] Field filtering (GraphQL, sparse fieldsets)
- [ ] Efficient serialization (Protocol Buffers, MessagePack)

---

## Frontend Performance

### Bundle Size

```javascript
// BAD - Import entire library
import _ from 'lodash';
_.map(items, fn);

// GOOD - Import only what's needed
import map from 'lodash/map';
map(items, fn);
```

### Rendering Performance

```jsx
// BAD - Unnecessary re-renders
function List({ items }) {
    return items.map(item => (
        <Item key={item.id} data={item} onClick={() => handle(item)} />
        // New function created each render
    ));
}

// GOOD - Memoized callbacks
function List({ items }) {
    const handleClick = useCallback((item) => handle(item), []);
    return items.map(item => (
        <Item key={item.id} data={item} onClick={handleClick} />
    ));
}
```

### Critical Rendering Path

- [ ] CSS in head, JS deferred/async
- [ ] Critical CSS inlined
- [ ] Images lazy loaded
- [ ] Fonts preloaded or using font-display
- [ ] Largest Contentful Paint (LCP) < 2.5s

**Review Checklist:**
- [ ] Tree shaking enabled
- [ ] Code splitting for routes
- [ ] Images optimized (WebP, responsive)
- [ ] Unnecessary re-renders prevented (React.memo, useMemo)
- [ ] Virtual scrolling for long lists
- [ ] Debounce/throttle for frequent events
- [ ] Web Vitals monitored (LCP, FID, CLS)
