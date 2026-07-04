---
name: react-native-optimistic-ui
description: Build, review, or debug optimistic UI flows in React Native and Expo apps. Use when implementing mutations that update the UI before server confirmation, adding rollback/retry behavior, handling temporary IDs, wiring TanStack Query or Apollo Client optimistic updates, testing race/error states, or fixing stale cache/list/detail synchronization after mobile network failures.
allowed-tools: Read Grep Glob Edit Write
disable-model-invocation: false
metadata:
  author: Luis Quiñones
  version: "1.0.0"
  category: mobile
---

# React Native Optimistic UI

## Quick Start

Treat optimistic UI as a small transaction:

1. Define the user intent and the exact local state or cache records it touches.
2. Create the optimistic patch with a stable client ID, status marker, and enough data to render immediately.
3. Prevent stale fetches from overwriting the optimistic value.
4. Snapshot or encode a rollback before applying the patch.
5. Reconcile success by replacing temporary/client fields with server fields.
6. Reconcile failure by rolling back or keeping a visible retry state.
7. Test fast success, slow success, hard failure, retry, duplicate tap, offline, and concurrent mutations.

Read [references/internet-resources.md](references/internet-resources.md) when choosing or verifying a library-specific implementation.

## Decision Tree

Use TanStack Query cache updates when the app already stores server data in query caches and the optimistic result affects multiple components. Prefer `onMutate`, `cancelQueries`, `setQueryData`, rollback data, and `invalidateQueries`.

Use TanStack Query UI-only pending variables when the optimistic item is only rendered beside one query result. Prefer `variables`, `isPending`, `isError`, `submittedAt`, and `useMutationState` for cross-component pending indicators.

Use Apollo Client when the app uses GraphQL normalized caching. Prefer `optimisticResponse`, `__typename`, object IDs, `cache.modify`, and temporary IDs for new objects.

Use RTK Query when the app already uses Redux Toolkit API slices. Prefer mutation `onQueryStarted`, `api.util.updateQueryData`, the returned patch object's `undo`, and tag invalidation for overlapping failures.

Use React `useOptimistic` for component-local optimistic state in React 19+ when there is no server-cache layer to update, or when the optimistic view is purely local to a component boundary. Wrap optimistic setters in `startTransition` or call them inside Action props.

Use local component or store state only when the data is not server cache data, or when the existing app has no query/cache layer. Keep the same transaction shape: patch, rollback, reconcile.

## React Native Rules

Make pending state visible but quiet: opacity, inline spinner, disabled destructive controls, or a small retry affordance. Avoid modal error flows for normal network failure.

Generate temporary IDs on the client for created records. Prefix them, for example `client:${uuid}`, so reconciliation can distinguish local records from server records.

Keep list order deterministic while pending. Use `submittedAt`, local creation time, or a sort key that will not jump when the server responds.

Disable or coalesce duplicate taps when the mutation is not idempotent. For idempotent actions, let concurrent optimistic mutations run but key each pending mutation separately.

Do not trust optimistic data for navigation permissions, payment state, destructive deletes, or security decisions. Render hope; enforce truth on the server.

For offline-capable apps, keep failed optimistic changes as retryable outbox items when losing user work would be worse than showing stale data. Otherwise roll back and show a local retry action.

Use `isInternetReachable`, not only `isConnected`, when deciding whether to queue or fire a mutation. A device can have a network link without internet reachability.

## TanStack Query Pattern

Use this shape for cache-wide optimistic updates:

```tsx
type Todo = {
  id: string;
  text: string;
  completed: boolean;
  syncStatus?: "pending" | "failed";
};

type AddTodoInput = {
  text: string;
};

type AddTodoContext = {
  previousTodos: Todo[] | undefined;
  optimisticId: string;
};

const addTodo = useMutation<Todo, Error, AddTodoInput, AddTodoContext>({
  mutationFn: apiCreateTodo,
  onMutate: async (input, context) => {
    await context.client.cancelQueries({ queryKey: ["todos"] });

    const previousTodos = context.client.getQueryData<Todo[]>(["todos"]);
    const optimisticId = `client:${Date.now()}`;
    const optimisticTodo: Todo = {
      id: optimisticId,
      text: input.text,
      completed: false,
      syncStatus: "pending",
    };

    context.client.setQueryData<Todo[]>(["todos"], (oldTodos = []) => [
      optimisticTodo,
      ...oldTodos,
    ]);

    return { previousTodos, optimisticId };
  },
  onError: (_error, _input, rollback, context) => {
    context.client.setQueryData(["todos"], rollback?.previousTodos);
  },
  onSuccess: (serverTodo, _input, rollback, context) => {
    context.client.setQueryData<Todo[]>(["todos"], (oldTodos = []) =>
      oldTodos.map((todo) =>
        todo.id === rollback.optimisticId ? serverTodo : todo,
      ),
    );
  },
  onSettled: (_data, _error, _input, _rollback, context) =>
    context.client.invalidateQueries({ queryKey: ["todos"] }),
});
```

For UI-only pending rows, render `mutation.variables` while `isPending`. If the mutation lives elsewhere, use `useMutationState` with a `mutationKey`, and use `submittedAt` as a stable key for concurrent pending rows.

## Apollo Client Pattern

Use this shape when the cache is normalized:

```tsx
type AddTodoVariables = {
  text: string;
};

const [addTodo] = useMutation<CreateTodoData, AddTodoVariables>(
  CREATE_ITEM_MUTATION,
  {
    optimisticResponse: ({ text }) => ({
      addTodo: {
        __typename: "Todo",
        id: `client:${Date.now()}`,
        text,
        completed: false,
      },
    }),
    update: (cache, result) => {
      const todo = result.data?.addTodo;
      if (!todo) return;

      cache.modify({
        fields: {
          todos(
            existingRefs: readonly Reference[] = [],
            { readField, toReference },
          ) {
            const newRef = toReference(todo);
            if (!newRef) return existingRefs;

            const exists = existingRefs.some(
              (ref) => readField("id", ref) === todo.id,
            );

            return exists ? existingRefs : [newRef, ...existingRefs];
          },
        },
      });
    },
  },
);
```

Ensure optimistic GraphQL objects include `id` and `__typename`. For creates, use a temporary ID and let Apollo remove the optimistic object when the server object arrives.

## RTK Query Pattern

Place optimistic cache patches inside endpoint lifecycle code, not inside React components:

```ts
type Post = {
  id: string;
  title: string;
};

const api = createApi({
  baseQuery,
  tagTypes: ["Post"],
  endpoints: (build) => ({
    getPost: build.query<Post, string>({
      query: (id) => `posts/${id}`,
      providesTags: (_result, _error, id) => [{ type: "Post", id }],
    }),
    updatePostTitle: build.mutation<Post, Pick<Post, "id" | "title">>({
      query: ({ id, title }) => ({
        url: `posts/${id}`,
        method: "PATCH",
        body: { title },
      }),
      async onQueryStarted({ id, title }, { dispatch, queryFulfilled }) {
        const patch = dispatch(
          api.util.updateQueryData("getPost", id, (draft) => {
            draft.title = title;
          }),
        );

        try {
          await queryFulfilled;
        } catch {
          patch.undo();
        }
      },
    }),
  }),
});
```

If several mutations can overlap on the same entity, prefer invalidating the affected tags on error instead of stacking several `.undo()` calls that may race.

## React `useOptimistic` Pattern

Use a reducer when base state can change while the mutation is pending:

```tsx
type Message = {
  id: string;
  body: string;
  pending?: boolean;
};

type AddMessageAction = {
  id: string;
  body: string;
};

const [optimisticMessages, addOptimisticMessage] = useOptimistic(
  messages,
  (currentMessages: Message[], action: AddMessageAction) => [
    ...currentMessages,
    { id: action.id, body: action.body, pending: true },
  ],
);

function handleSend(body: string) {
  const id = `client:${Date.now()}`;

  startTransition(async () => {
    addOptimisticMessage({ id, body });
    await sendMessage({ clientId: id, body });
  });
}
```

Use this for local UI state. If TanStack Query, Apollo, or RTK Query owns the server data, update that cache instead so list/detail screens converge.

## Offline Queue Pattern

Use an outbox when the app should preserve user intent offline:

```ts
type OutboxItem = {
  clientId: string;
  kind: "create-message";
  payload: {
    body: string;
  };
  createdAt: number;
  attempts: number;
};
```

Persist outbox items before rendering the optimistic row if process death would lose the mutation. Release the queue on confirmed internet reachability, throttle releases, and make server endpoints idempotent with a `clientId`.

For Redux apps using `react-native-offline`, queue retryable actions with `meta.retry` and define dismiss actions for intents that should not replay after navigation or sign-out.

## Review Checklist

- Mutation has a clear rollback or retry path.
- Pending rows have stable keys and cannot collide with server IDs.
- Stale queries are canceled or stale responses are ignored before patching.
- Success reconciliation replaces optimistic records instead of duplicating them.
- Failure behavior preserves user input when retry matters.
- Concurrent mutations are keyed independently.
- List and detail caches stay consistent.
- Offline behavior is explicit: rollback, retryable failed item, or persisted outbox.
- Connectivity checks distinguish link state from internet reachability.
- Tests cover slow network, failure, retry, duplicate action, and success after optimistic render.
