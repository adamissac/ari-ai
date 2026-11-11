# inventory

## Availability

- A warehouse keeps `safety_stock` units of every item that are never promised
  to customers.
- Available units = on hand - reserved - safety stock, never below zero.
- A reservation succeeds only when the quantity is at most the available units.
