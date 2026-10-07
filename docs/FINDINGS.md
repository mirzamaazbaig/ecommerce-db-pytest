# Findings

What the database tests found in the application under test, and how each one was closed. The defect log in the application repository has the same entries (D7, S1 to S7).

| ID | Finding | Found by | Status |
|---|---|---|---|
| D7 | Deleting a product that customers have ordered returned `500 Server error` (the foreign key error from PostgreSQL leaked out) | `test_deleting_a_product_that_has_been_ordered_is_a_clear_conflict_not_a_server_error` | Fixed: `409` with a message |
| S1 | `products.stock` could be negative or NULL | `test_stock_cannot_be_negative`, `test_stock_cannot_be_null` | Fixed by migration 002 |
| S2 | `products.price` could be negative | `test_a_price_cannot_be_negative` | Fixed |
| S3 | An order line could have quantity 0 or less, or a negative price | `test_an_order_line_quantity_must_be_positive`, `test_an_order_line_price_cannot_be_negative` | Fixed |
| S4 | An order line could have no order and no product | `test_an_order_line_must_belong_to_an_order_and_a_product` | Fixed |
| S5 | An order could have a negative total or no user | `test_an_order_total_cannot_be_negative`, `test_an_order_must_belong_to_a_user` | Fixed |
| S6 | `users.role` accepted any text | `test_a_user_role_must_be_user_or_admin` | Fixed |
| S7 | Migration 001 added dummy reviews again on every run; `migrate.js` ran only migration 001 | `test_migrating_again_does_not_add_the_dummy_reviews_again` | Fixed |

## How the gaps were handled

While a safeguard was missing, its test was written as the behaviour we want and marked `xfail(strict=True)`: the suite stayed green, and the moment the safeguard existed the build went red (`XPASS(strict)`), which forced the marker to be removed. Running the suite after adding migration 002 produced exactly that: 13 strict expected failures turned into failures, and removing the markers left 68 passing tests (73 with the migration tests).

## Open questions (not changed, need a product decision)

- Which order statuses exist? Only `pending` is ever written; a `CHECK` would be a guess.
- Should a customer be able to review the same product twice? The schema allows it.
- Should emails be case-insensitive? `A@x.com` and `a@x.com` are different accounts today. A unique index on `lower(email)` would also need a friendly error in the registration endpoint.
- Test data: the shared test database collects orders whose lines were deleted by other suites' cleanup, so "total equals sum of lines" is asserted on orders this suite creates, not on every order in the database.
