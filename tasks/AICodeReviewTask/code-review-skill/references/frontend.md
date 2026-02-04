# Frontend Code Review

React, Vue, Angular, and modern frontend best practices.

## Table of Contents
1. [React](#react)
2. [Vue](#vue)
3. [Angular](#angular)
4. [Vite & Build Tools](#vite--build-tools)
5. [State Management](#state-management)
6. [Accessibility](#accessibility)
7. [Testing](#testing)

---

## React

### Component Patterns

```tsx
// Prefer function components with hooks
function UserProfile({ userId }: { userId: string }) {
    const { data: user, isLoading, error } = useUser(userId);

    if (isLoading) return <Spinner />;
    if (error) return <ErrorMessage error={error} />;

    return <Profile user={user} />;
}

// Props interface
interface ButtonProps {
    variant: 'primary' | 'secondary';
    onClick: () => void;
    children: React.ReactNode;
    disabled?: boolean;
}

// Use children prop properly
function Card({ children, title }: { children: React.ReactNode; title: string }) {
    return (
        <div className="card">
            <h2>{title}</h2>
            {children}
        </div>
    );
}
```

### Hooks Best Practices

```tsx
// BAD - Dependencies missing
useEffect(() => {
    fetchUser(userId);
}, []); // Missing userId dependency!

// GOOD - All dependencies included
useEffect(() => {
    fetchUser(userId);
}, [userId]);

// BAD - Object/array in dependencies (new reference each render)
useEffect(() => {
    doSomething(options);
}, [options]); // Runs every render if options = { ... }

// GOOD - Memoize or use primitive values
const memoizedOptions = useMemo(() => options, [options.key1, options.key2]);
useEffect(() => {
    doSomething(memoizedOptions);
}, [memoizedOptions]);

// Custom hooks for reusable logic
function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedValue(value), delay);
        return () => clearTimeout(timer);
    }, [value, delay]);

    return debouncedValue;
}
```

### Performance Optimization

```tsx
// React.memo for expensive renders
const ExpensiveList = React.memo(function ExpensiveList({ items }: Props) {
    return items.map(item => <Item key={item.id} {...item} />);
});

// useCallback for stable function references
function Parent() {
    const handleClick = useCallback((id: string) => {
        setSelected(id);
    }, []); // Stable reference

    return <List items={items} onItemClick={handleClick} />;
}

// useMemo for expensive computations
const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => a.name.localeCompare(b.name));
}, [items]);

// Lazy loading components
const HeavyComponent = React.lazy(() => import('./HeavyComponent'));

function App() {
    return (
        <Suspense fallback={<Spinner />}>
            <HeavyComponent />
        </Suspense>
    );
}
```

**Review Checklist:**
- [ ] useEffect dependencies complete
- [ ] No inline objects/arrays in dependencies
- [ ] Keys on list items (not index for dynamic lists)
- [ ] React.memo where beneficial
- [ ] Cleanup in useEffect when needed
- [ ] No direct DOM manipulation

---

## Vue

### Composition API (Vue 3)

```vue
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';

// Refs
const count = ref(0);
const user = ref<User | null>(null);

// Computed
const doubleCount = computed(() => count.value * 2);

// Watch
watch(count, (newVal, oldVal) => {
    console.log(`Changed from ${oldVal} to ${newVal}`);
});

// Lifecycle
onMounted(async () => {
    user.value = await fetchUser();
});

// Methods (just regular functions)
function increment() {
    count.value++;
}
</script>

<template>
    <button @click="increment">{{ count }}</button>
</template>
```

### Composables

```typescript
// composables/useUser.ts
export function useUser(userId: Ref<string>) {
    const user = ref<User | null>(null);
    const loading = ref(false);
    const error = ref<Error | null>(null);

    async function fetchUser() {
        loading.value = true;
        error.value = null;
        try {
            user.value = await api.getUser(userId.value);
        } catch (e) {
            error.value = e as Error;
        } finally {
            loading.value = false;
        }
    }

    watch(userId, fetchUser, { immediate: true });

    return { user, loading, error, refetch: fetchUser };
}
```

### Props and Emits

```vue
<script setup lang="ts">
// Type-safe props
interface Props {
    title: string;
    count?: number;
}

const props = withDefaults(defineProps<Props>(), {
    count: 0
});

// Type-safe emits
const emit = defineEmits<{
    (e: 'update', value: number): void;
    (e: 'close'): void;
}>();

function handleClick() {
    emit('update', props.count + 1);
}
</script>
```

**Review Checklist:**
- [ ] Composition API preferred (Vue 3)
- [ ] Composables for reusable logic
- [ ] Props and emits typed
- [ ] v-model for two-way binding
- [ ] Key on v-for items
- [ ] Computed for derived state

---

## Angular

### Component Structure

```typescript
@Component({
    selector: 'app-user-profile',
    standalone: true,
    imports: [CommonModule, RouterModule],
    template: `
        @if (user(); as user) {
            <h1>{{ user.name }}</h1>
        } @else {
            <app-spinner />
        }
    `,
    changeDetection: ChangeDetectionStrategy.OnPush
})
export class UserProfileComponent {
    private userService = inject(UserService);

    userId = input.required<string>();

    user = computed(() => {
        // Derived from signal
    });

    // Or with toSignal for async
    user$ = toSignal(this.userService.getUser(this.userId()));
}
```

### Signals (Angular 16+)

```typescript
@Component({ ... })
export class CounterComponent {
    // Writable signal
    count = signal(0);

    // Computed signal
    doubleCount = computed(() => this.count() * 2);

    // Effect for side effects
    constructor() {
        effect(() => {
            console.log(`Count is now ${this.count()}`);
        });
    }

    increment() {
        this.count.update(c => c + 1);
    }
}
```

### Services and DI

```typescript
@Injectable({
    providedIn: 'root'
})
export class UserService {
    private http = inject(HttpClient);

    getUser(id: string): Observable<User> {
        return this.http.get<User>(`/api/users/${id}`);
    }

    // Signal-based state
    private usersSignal = signal<User[]>([]);
    users = this.usersSignal.asReadonly();

    loadUsers() {
        this.http.get<User[]>('/api/users').subscribe(users => {
            this.usersSignal.set(users);
        });
    }
}
```

**Review Checklist:**
- [ ] Standalone components (Angular 15+)
- [ ] Signals for reactive state (Angular 16+)
- [ ] OnPush change detection
- [ ] inject() over constructor injection
- [ ] Observables properly unsubscribed
- [ ] trackBy for ngFor

---

## Vite & Build Tools

### Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
    plugins: [react()],
    build: {
        rollupOptions: {
            output: {
                // Code splitting
                manualChunks: {
                    vendor: ['react', 'react-dom'],
                    utils: ['lodash-es', 'date-fns']
                }
            }
        },
        // Minification
        minify: 'esbuild',
        // Source maps for production debugging
        sourcemap: true
    },
    // Environment variables
    envPrefix: 'APP_'
});
```

### Bundle Optimization

```typescript
// Dynamic imports for code splitting
const AdminPanel = lazy(() => import('./AdminPanel'));

// Tree-shakeable imports
import { debounce } from 'lodash-es'; // Good
import _ from 'lodash'; // Bad - imports everything

// Environment-aware code
if (import.meta.env.DEV) {
    // Development only
}
```

**Review Checklist:**
- [ ] Code splitting configured
- [ ] Tree-shakeable imports
- [ ] Assets optimized (images, fonts)
- [ ] Environment variables properly prefixed
- [ ] Bundle size analyzed

---

## State Management

### React Query / TanStack Query

```tsx
function UserList() {
    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ['users'],
        queryFn: fetchUsers,
        staleTime: 5 * 60 * 1000, // 5 minutes
    });

    const mutation = useMutation({
        mutationFn: createUser,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['users'] });
        }
    });
}
```

### Zustand (React)

```typescript
interface UserStore {
    user: User | null;
    setUser: (user: User) => void;
    logout: () => void;
}

const useUserStore = create<UserStore>((set) => ({
    user: null,
    setUser: (user) => set({ user }),
    logout: () => set({ user: null })
}));

// Usage
const user = useUserStore((state) => state.user);
const setUser = useUserStore((state) => state.setUser);
```

### Pinia (Vue)

```typescript
export const useUserStore = defineStore('user', () => {
    const user = ref<User | null>(null);
    const isLoggedIn = computed(() => user.value !== null);

    async function login(credentials: Credentials) {
        user.value = await api.login(credentials);
    }

    function logout() {
        user.value = null;
    }

    return { user, isLoggedIn, login, logout };
});
```

**Review Checklist:**
- [ ] Server state vs client state separated
- [ ] React Query/SWR for server state
- [ ] Minimal global state
- [ ] Selectors for derived state
- [ ] Actions for state mutations

---

## Accessibility

### ARIA and Semantic HTML

```tsx
// Use semantic elements
<nav aria-label="Main navigation">
    <ul>
        <li><a href="/">Home</a></li>
    </ul>
</nav>

// Buttons for actions, links for navigation
<button onClick={handleSubmit}>Submit</button> // Action
<a href="/about">About</a> // Navigation

// Form accessibility
<label htmlFor="email">Email</label>
<input
    id="email"
    type="email"
    aria-describedby="email-hint"
    aria-invalid={hasError}
/>
<span id="email-hint">We'll never share your email</span>

// Loading states
<div role="status" aria-live="polite">
    {isLoading ? 'Loading...' : null}
</div>

// Modal accessibility
<dialog
    role="dialog"
    aria-modal="true"
    aria-labelledby="dialog-title"
>
    <h2 id="dialog-title">Confirm Action</h2>
</dialog>
```

### Keyboard Navigation

```tsx
// Focusable elements
<div
    tabIndex={0}
    role="button"
    onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            handleClick();
        }
    }}
>
    Custom Button
</div>

// Skip links
<a href="#main-content" className="skip-link">
    Skip to main content
</a>
```

**Review Checklist:**
- [ ] Semantic HTML elements used
- [ ] ARIA labels on interactive elements
- [ ] Keyboard navigation works
- [ ] Color contrast sufficient (4.5:1)
- [ ] Focus indicators visible
- [ ] Images have alt text

---

## Testing

### Component Testing (React Testing Library)

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

test('submits form with user data', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<UserForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
            email: 'test@example.com',
            password: 'password123'
        });
    });
});
```

### E2E Testing (Playwright)

```typescript
import { test, expect } from '@playwright/test';

test('user can login', async ({ page }) => {
    await page.goto('/login');

    await page.fill('[name="email"]', 'test@example.com');
    await page.fill('[name="password"]', 'password123');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('h1')).toHaveText('Welcome');
});
```

**Review Checklist:**
- [ ] Components tested in isolation
- [ ] User interactions simulated
- [ ] Async operations awaited
- [ ] Accessibility tested
- [ ] Critical paths have E2E tests
