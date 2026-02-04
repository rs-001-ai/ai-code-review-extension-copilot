# Backend Framework Code Review

FastAPI, Flask, Express, Spring Boot, and ASP.NET Core best practices.

## Table of Contents
1. [FastAPI (Python)](#fastapi-python)
2. [Flask (Python)](#flask-python)
3. [Express (Node.js)](#express-nodejs)
4. [Spring Boot (Java)](#spring-boot-java)
5. [ASP.NET Core (C#)](#aspnet-core-c)
6. [API Design Patterns](#api-design-patterns)
7. [Database Patterns](#database-patterns)

---

## FastAPI (Python)

### Route Structure

```python
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI()

# Pydantic models for validation
class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=100)
    name: str = Field(..., min_length=1, max_length=50)

class UserResponse(BaseModel):
    id: int
    email: str
    name: str

    class Config:
        from_attributes = True  # For ORM models

# Dependency injection
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    user = await verify_token(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    return user

# Routes with proper typing
@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

### Async Best Practices

```python
# BAD - Blocking call in async function
@app.get("/data")
async def get_data():
    result = requests.get(url)  # Blocks!
    return result.json()

# GOOD - Use async HTTP client
@app.get("/data")
async def get_data():
    async with httpx.AsyncClient() as client:
        result = await client.get(url)
    return result.json()

# BAD - Sync database call
@app.get("/users")
async def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()  # Blocks!

# GOOD - Use async database
@app.get("/users")
async def get_users(db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(User))
    return result.scalars().all()
```

**Review Checklist:**
- [ ] Pydantic models for request/response
- [ ] Dependency injection for services
- [ ] Async handlers when I/O bound
- [ ] No blocking calls in async routes
- [ ] HTTPException with proper status codes
- [ ] response_model for documentation

---

## Flask (Python)

### Application Structure

```python
# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)

    from .api import users_bp
    app.register_blueprint(users_bp, url_prefix='/api/users')

    return app

# app/api/users.py
from flask import Blueprint, request, jsonify
from marshmallow import Schema, fields, validate

users_bp = Blueprint('users', __name__)

class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    email = fields.Email(required=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=50))

user_schema = UserSchema()
users_schema = UserSchema(many=True)

@users_bp.route('/', methods=['POST'])
def create_user():
    errors = user_schema.validate(request.json)
    if errors:
        return jsonify(errors), 400

    user = User(**user_schema.load(request.json))
    db.session.add(user)
    db.session.commit()

    return user_schema.dump(user), 201

@users_bp.errorhandler(404)
def not_found(e):
    return jsonify(error='Not found'), 404
```

### Error Handling

```python
from flask import Flask, jsonify

app = Flask(__name__)

class APIError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code

@app.errorhandler(APIError)
def handle_api_error(error):
    return jsonify(error=error.message), error.status_code

@app.errorhandler(500)
def handle_server_error(error):
    return jsonify(error='Internal server error'), 500

# Usage
@app.route('/users/<int:user_id>')
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        raise APIError('User not found', 404)
    return user_schema.dump(user)
```

**Review Checklist:**
- [ ] Application factory pattern
- [ ] Blueprints for modular routes
- [ ] Marshmallow for validation
- [ ] Error handlers registered
- [ ] Database sessions properly managed
- [ ] Config by environment

---

## Express (Node.js)

### Application Structure

```typescript
// src/app.ts
import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import { errorHandler } from './middleware/errorHandler';
import { userRouter } from './routes/users';

const app = express();

// Security middleware
app.use(helmet());
app.use(cors());
app.use(express.json({ limit: '10kb' }));

// Routes
app.use('/api/users', userRouter);

// Error handling (must be last)
app.use(errorHandler);

export default app;
```

### Route Handlers

```typescript
// src/routes/users.ts
import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { UserService } from '../services/UserService';

const router = Router();

// Validation schema
const createUserSchema = z.object({
    email: z.string().email(),
    name: z.string().min(1).max(50)
});

// Async handler wrapper
const asyncHandler = (fn: Function) => (
    req: Request, res: Response, next: NextFunction
) => Promise.resolve(fn(req, res, next)).catch(next);

router.post('/', asyncHandler(async (req: Request, res: Response) => {
    const data = createUserSchema.parse(req.body);
    const user = await UserService.create(data);
    res.status(201).json(user);
}));

router.get('/:id', asyncHandler(async (req: Request, res: Response) => {
    const user = await UserService.findById(req.params.id);
    if (!user) {
        throw new NotFoundError('User not found');
    }
    res.json(user);
}));

export { router as userRouter };
```

### Error Handling

```typescript
// src/middleware/errorHandler.ts
import { Request, Response, NextFunction } from 'express';
import { ZodError } from 'zod';

export class AppError extends Error {
    constructor(
        public message: string,
        public statusCode: number = 500,
        public isOperational = true
    ) {
        super(message);
    }
}

export class NotFoundError extends AppError {
    constructor(message = 'Resource not found') {
        super(message, 404);
    }
}

export function errorHandler(
    err: Error,
    req: Request,
    res: Response,
    next: NextFunction
) {
    if (err instanceof ZodError) {
        return res.status(400).json({
            error: 'Validation failed',
            details: err.errors
        });
    }

    if (err instanceof AppError) {
        return res.status(err.statusCode).json({
            error: err.message
        });
    }

    console.error(err);
    res.status(500).json({ error: 'Internal server error' });
}
```

**Review Checklist:**
- [ ] Security middleware (helmet, cors)
- [ ] Input validation (Zod, Joi)
- [ ] Async errors caught
- [ ] Centralized error handler
- [ ] Request body size limited
- [ ] TypeScript types for req/res

---

## Spring Boot (Java)

### Controller Layer

```java
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
@Validated
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

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Map<String, String> handleValidation(MethodArgumentNotValidException ex) {
        return ex.getBindingResult().getFieldErrors().stream()
            .collect(Collectors.toMap(
                FieldError::getField,
                FieldError::getDefaultMessage
            ));
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
    private final UserMapper userMapper;

    public Optional<UserDto> findById(Long id) {
        return userRepository.findById(id)
            .map(userMapper::toDto);
    }

    @Transactional
    public UserDto create(CreateUserRequest request) {
        if (userRepository.existsByEmail(request.email())) {
            throw new ConflictException("Email already exists");
        }

        var user = userMapper.toEntity(request);
        user = userRepository.save(user);
        return userMapper.toDto(user);
    }
}
```

### Exception Handling

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(NotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ErrorResponse handleNotFound(NotFoundException ex) {
        return new ErrorResponse(ex.getMessage());
    }

    @ExceptionHandler(ConflictException.class)
    @ResponseStatus(HttpStatus.CONFLICT)
    public ErrorResponse handleConflict(ConflictException ex) {
        return new ErrorResponse(ex.getMessage());
    }

    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ErrorResponse handleGeneric(Exception ex) {
        log.error("Unexpected error", ex);
        return new ErrorResponse("Internal server error");
    }
}

record ErrorResponse(String error) {}
```

**Review Checklist:**
- [ ] Constructor injection (not @Autowired on fields)
- [ ] @Transactional at service layer
- [ ] @Valid for input validation
- [ ] Global exception handler
- [ ] DTO mapping (not exposing entities)
- [ ] readOnly = true for read operations

---

## ASP.NET Core (C#)

### Controller Layer

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
    public async Task<ActionResult<UserDto>> GetUser(
        int id,
        CancellationToken cancellationToken)
    {
        var user = await _userService.GetByIdAsync(id, cancellationToken);
        if (user is null)
            return NotFound();

        return Ok(user);
    }

    [HttpPost]
    [ProducesResponseType(typeof(UserDto), StatusCodes.Status201Created)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    public async Task<ActionResult<UserDto>> CreateUser(
        [FromBody] CreateUserRequest request,
        CancellationToken cancellationToken)
    {
        var user = await _userService.CreateAsync(request, cancellationToken);
        return CreatedAtAction(nameof(GetUser), new { id = user.Id }, user);
    }
}
```

### Service Layer

```csharp
public interface IUserService
{
    Task<UserDto?> GetByIdAsync(int id, CancellationToken cancellationToken = default);
    Task<UserDto> CreateAsync(CreateUserRequest request, CancellationToken cancellationToken = default);
}

public class UserService : IUserService
{
    private readonly AppDbContext _context;
    private readonly IMapper _mapper;

    public UserService(AppDbContext context, IMapper mapper)
    {
        _context = context;
        _mapper = mapper;
    }

    public async Task<UserDto?> GetByIdAsync(int id, CancellationToken cancellationToken = default)
    {
        var user = await _context.Users
            .AsNoTracking()
            .FirstOrDefaultAsync(u => u.Id == id, cancellationToken);

        return user is null ? null : _mapper.Map<UserDto>(user);
    }

    public async Task<UserDto> CreateAsync(CreateUserRequest request, CancellationToken cancellationToken = default)
    {
        var user = _mapper.Map<User>(request);
        _context.Users.Add(user);
        await _context.SaveChangesAsync(cancellationToken);

        return _mapper.Map<UserDto>(user);
    }
}
```

### Dependency Injection

```csharp
// Program.cs
var builder = WebApplication.CreateBuilder(args);

builder.Services.AddScoped<IUserService, UserService>();
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(builder.Configuration.GetConnectionString("Default")));

builder.Services.AddAutoMapper(typeof(MappingProfile));

var app = builder.Build();

app.UseExceptionHandler("/error");
app.MapControllers();

app.Run();
```

**Review Checklist:**
- [ ] CancellationToken passed through
- [ ] Async/await used correctly
- [ ] Proper DI lifetime (Scoped for DbContext)
- [ ] AsNoTracking for read queries
- [ ] ProducesResponseType for OpenAPI
- [ ] Global exception handling

---

## API Design Patterns

### RESTful Conventions

```
GET    /api/users           # List users (paginated)
POST   /api/users           # Create user
GET    /api/users/{id}      # Get single user
PUT    /api/users/{id}      # Replace user
PATCH  /api/users/{id}      # Update user
DELETE /api/users/{id}      # Delete user

GET    /api/users/{id}/orders  # Get user's orders
POST   /api/users/{id}/orders  # Create order for user
```

### Pagination

```json
// Request
GET /api/users?page=1&limit=20&sort=name&order=asc

// Response
{
    "data": [...],
    "meta": {
        "page": 1,
        "limit": 20,
        "total": 150,
        "totalPages": 8
    },
    "links": {
        "self": "/api/users?page=1&limit=20",
        "next": "/api/users?page=2&limit=20",
        "prev": null
    }
}
```

### Error Responses

```json
// Validation error (400)
{
    "error": "Validation failed",
    "details": [
        { "field": "email", "message": "Invalid email format" },
        { "field": "name", "message": "Name is required" }
    ]
}

// Not found (404)
{
    "error": "User not found"
}

// Server error (500)
{
    "error": "Internal server error",
    "requestId": "abc123"  // For debugging
}
```

**Review Checklist:**
- [ ] Consistent URL naming (plural nouns)
- [ ] Proper HTTP methods
- [ ] Pagination for lists
- [ ] Consistent error format
- [ ] Idempotent where expected

---

## Database Patterns

### Repository Pattern

```typescript
// Repository interface
interface UserRepository {
    findById(id: string): Promise<User | null>;
    findByEmail(email: string): Promise<User | null>;
    save(user: User): Promise<User>;
    delete(id: string): Promise<void>;
}

// Implementation (can be swapped)
class PrismaUserRepository implements UserRepository {
    constructor(private prisma: PrismaClient) {}

    async findById(id: string): Promise<User | null> {
        return this.prisma.user.findUnique({ where: { id } });
    }

    async save(user: User): Promise<User> {
        return this.prisma.user.upsert({
            where: { id: user.id },
            create: user,
            update: user
        });
    }
}
```

### Unit of Work

```python
# Transaction management
async def transfer_funds(from_id: int, to_id: int, amount: Decimal):
    async with db.begin():  # Transaction
        from_account = await db.get(Account, from_id, with_for_update=True)
        to_account = await db.get(Account, to_id, with_for_update=True)

        if from_account.balance < amount:
            raise InsufficientFundsError()

        from_account.balance -= amount
        to_account.balance += amount
        # Commits automatically, rolls back on exception
```

### N+1 Query Prevention

```python
# BAD - N+1 queries
users = await db.execute(select(User))
for user in users.scalars():
    orders = await db.execute(select(Order).where(Order.user_id == user.id))

# GOOD - Eager loading
users = await db.execute(
    select(User).options(selectinload(User.orders))
)

# GOOD - Join
users = await db.execute(
    select(User).join(User.orders).options(contains_eager(User.orders))
)
```

**Review Checklist:**
- [ ] Transactions for multi-step operations
- [ ] N+1 queries prevented
- [ ] Connection pooling configured
- [ ] Indexes on queried columns
- [ ] Soft delete if required
- [ ] Audit fields (created_at, updated_at)
