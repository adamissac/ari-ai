# webhooks

## Delivery rules

- The provider may deliver the same event id more than once, in the same batch
  or in a later one.
- Each event id is handled at most once for the lifetime of a Consumer.
