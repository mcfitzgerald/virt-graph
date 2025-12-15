# Benchmark Questions for Supply Chain Examples

60 business questions for demand-driven pattern discovery.

1. Find the supplier with code "ACME-001"
2. List all tier 1 suppliers
3. What parts can supplier "GlobalTech Industries" supply?
4. Who is the primary supplier for part "CHIP-001"?
5. Which suppliers have ISO 9001 certification?
6. What are the direct components of product "Turbo Encabulator"?
7. What is the current inventory of part "CHIP-001" at "Chicago Warehouse"?
8. List all pending orders for customer "Acme Industries"
9. Total revenue by customer for last quarter
10. Which parts are below their reorder point?
11. Find all tier 2 suppliers of "Acme Corp"
12. Find all tier 2 AND tier 3 suppliers upstream from "Acme Corp"
13. Who are the downstream customers (buyers) of "Pacific Components"?
14. Trace the complete supply path from "Eastern Electronics" to any tier 1
15. What is the maximum depth of our supplier network?
16. Which tier 1 suppliers have the deepest supply chains?
17. Find all suppliers that are exactly 2 hops from "GlobalTech Industries"
18. Which suppliers appear in multiple supply chains (shared suppliers)?
19. Full BOM explosion for product "Turbo Encabulator" (all levels)
20. Full BOM explosion with quantities for "Flux Capacitor"
21. Where is part "CHIP-001" used? (where-used analysis)
22. Find all products that contain part "RESISTOR-100" at any level
23. Calculate total component cost for "Turbo Encabulator"
24. What is the deepest BOM level for any product?
25. Find all leaf components (no sub-parts) in "Turbo Encabulator"
26. Which parts are used in BOTH "Turbo Encabulator" AND "Flux Capacitor"?
27. Find the critical path (longest chain) in "Turbo Encabulator" BOM
28. If part "RESISTOR-100" fails, trace impact through all BOM levels
29. Find the shortest route (by distance) from "Chicago Warehouse" to "LA Distribution Center"
30. What is the cheapest route from "New York Factory" to "Seattle Warehouse"?
31. Find the fastest route from "Chicago Warehouse" to "Miami Hub"
32. Show all routes from Chicago to LA with total distance under 3000km
33. Find top 3 alternative routes from New York to LA by cost
34. What is the minimum number of hops from Chicago to any West Coast facility?
35. Find a route from Chicago to Miami that avoids "Denver Hub"
36. Which facility is most central in the transport network?
37. Which facility has the most direct connections?
38. Rank facilities by their importance to network flow
39. Are there any isolated facilities (no routes in or out)?
40. If "Denver Hub" goes offline, which facility pairs lose connectivity?
41. Do we have sufficient inventory to build 100 units of "Turbo Encabulator"?
42. Which components of "Flux Capacitor" are currently out of stock?
43. Find all certified suppliers in "Acme Corp's" tier 2+ supply network
44. What is the total value at risk if "Pacific Components" fails?
45. If "Acme Corp" fails, which products lose ALL their suppliers?
46. Identify single points of failure in "Turbo Encabulator" supply chain
47. Find the cheapest shipping route for order "ORD-2024-001"
48. Which suppliers could fulfill order "ORD-2024-001" within 5 days?
49. Rank facilities by criticality: connections × inventory value
50. If "Denver Hub" fails, what's the cost increase to ship pending orders?
51. Calculate the total transport distance to assemble one "Turbo Encabulator" (sum of distances from each leaf component's primary supplier to "Chicago Warehouse")
52. Which single transport_route carries the highest volume of distinct component types required for "Flux Capacitor"?
53. Find the shortest path from "Chicago Warehouse" to "Miami Hub" that only passes through facilities with at least 50 units of "CHIP-001" in stock
54. Find a route for order "ORD-2024-001" where total transit time < 48 hours but cost is minimized
55. Find any Tier 3 supplier that is the sole source for a part used in more than 3 different Tier 1 products
56. Are there any loops in the supply chain? (Supplier A sells to B, B sells to A)
57. Compare the theoretical transit_time_hours in transport_routes vs actual average time for shipments between "Chicago Warehouse" and "Miami Hub"
58. If "Denver Hub" is destroyed, calculate the total value of orders that cannot be fulfilled because required stock is trapped there
59. A batch of "RESISTOR-100" from "GlobalTech Industries" is defective. Find all customers who received a shipment containing a product using this part
60. Find all parts in bill_of_materials that are children but have no product_components entry linking them to a top-level product (dead stock)
