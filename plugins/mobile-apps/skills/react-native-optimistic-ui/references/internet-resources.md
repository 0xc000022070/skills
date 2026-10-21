# Internet Resources

Use these sources when implementing or checking library-specific optimistic UI behavior.

## TanStack Query

- Source: https://raw.githubusercontent.com/TanStack/query/main/docs/framework/react/guides/optimistic-updates.md
- Use for React and React Native apps using `@tanstack/react-query`.
- Key points: optimistic UI can be done through pending mutation variables or direct cache writes; direct cache writes use `onMutate`, `cancelQueries`, `getQueryData`, `setQueryData`, rollback data, and `invalidateQueries`; `useMutationState` plus `mutationKey` exposes pending variables outside the mutating component; `submittedAt` helps key concurrent optimistic rows.
- Prefer UI-only variables when one component needs the optimistic rendering. Prefer cache writes when multiple components need the same optimistic state.

## Apollo Client

- Source: https://raw.githubusercontent.com/apollographql/apollo-client/main/docs/source/performance/optimistic-ui.mdx
- Use for React Native apps using GraphQL and Apollo normalized cache.
- Key points: `optimisticResponse` must match the mutation response shape; objects need `id` and `__typename` for cache identity; Apollo stores a separate optimistic layer, not a permanent overwrite; GraphQL errors discard the optimistic layer; creates need temporary IDs; `optimisticResponse` can return the `IGNORE` sentinel when the update should be skipped.
- Combine `optimisticResponse` with `update` or field policies when the mutation must insert, remove, or reorder list items.

## RTK Query

- Source: https://raw.githubusercontent.com/reduxjs/redux-toolkit/master/docs/rtk-query/usage/manual-cache-updates.mdx
- Use for apps that already use Redux Toolkit API slices.
- Key points: manual cache updates are useful for optimistic and pessimistic updates; optimistic updates belong in mutation `onQueryStarted`; use `api.util.updateQueryData` to patch existing cache entries; use the returned patch object's `.undo()` to roll back; for overlapping mutations, invalidating tags and refetching can be safer than undoing patches.
- Source for patch utilities: https://raw.githubusercontent.com/reduxjs/redux-toolkit/master/docs/rtk-query/api/created-api/api-slice-utils.mdx

## React `useOptimistic`

- Source: https://raw.githubusercontent.com/reactjs/react.dev/main/src/content/reference/react/useOptimistic.md
- Use for React 19+ local optimistic state when no server-cache library owns the data.
- Key points: `useOptimistic(value, reducer?)` returns the optimistic state and a setter; call the setter inside an Action or `startTransition`; reducers help when the base state may change while the async work is pending; failed Actions revert to the current base value; pending state can be detected by comparing optimistic and base values or by adding a pending flag.
- Use reducers for lists, counters, and multi-field updates. Avoid stale direct value replacement when concurrent updates can happen.

## React Native Networking And Reachability

- Source: https://raw.githubusercontent.com/react/react-native-website/main/docs/network.md
- Use for baseline `fetch` behavior and failure handling in React Native.
- Key points: network requests can fail and need `try`/`catch`; UI should not stay in infinite loading when request failure is normal mobile behavior.

## NetInfo

- Source: https://raw.githubusercontent.com/react-native-netinfo/react-native-netinfo/master/README.md
- Use to detect network type, connection state, and internet reachability.
- Key points: `useNetInfo`, `fetch`, and `addEventListener` expose current network state; `isConnected` means an active network connection, while `isInternetReachable` indicates whether internet access is reachable; reachability can be configured with a URL, method, timeouts, and tests.
- For optimistic UI, prefer outbox release based on internet reachability, not only network link state.

## react-native-offline

- Source: https://raw.githubusercontent.com/rgommezz/react-native-offline/master/README.md
- Use for Redux-based React Native apps needing offline/online rendering, connectivity state, middleware interception, and an offline action queue.
- Key points: provides a network reducer, provider components, hook, saga, middleware, and offline queue; the queue can re-dispatch actions when connection returns; duplicate action comparison and dismiss actions can control replay behavior; middleware should run before async middleware.
- Useful when optimistic UI must preserve intent across offline periods instead of rolling back immediately.

## Package Anchors

- TanStack Query npm: https://www.npmjs.com/package/@tanstack/react-query
- Apollo Client npm: https://www.npmjs.com/package/@apollo/client
- Redux Toolkit npm: https://www.npmjs.com/package/@reduxjs/toolkit
- NetInfo npm: https://www.npmjs.com/package/@react-native-community/netinfo
- react-native-offline npm: https://www.npmjs.com/package/react-native-offline

## Search Terms For More Evidence

Use these exact terms when more current or issue-specific evidence is needed:

- `site:github.com TanStack Query optimistic updates onMutate rollback`
- `site:github.com Apollo Client optimisticResponse temporary id cache.modify`
- `site:github.com RTK Query optimistic updates updateQueryData undo`
- `site:github.com React useOptimistic reducer pending rollback`
- `site:github.com React Native NetInfo isInternetReachable optimistic queue`
- `site:github.com react-native-offline offline queue retry dismiss`
- `site:stackoverflow.com react native optimistic update rollback react query`
- `site:npmjs.com react native optimistic ui`
