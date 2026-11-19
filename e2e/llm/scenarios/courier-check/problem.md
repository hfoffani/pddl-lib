A courier van starts at the depot. It must deliver three parcels and then
return to the depot:

- the medicine, waiting at the harbor, goes to the hospital;
- the books, waiting at the mill, go to the school;
- the tools, waiting at the airport, go to the castle.

The van can carry any number of parcels. Loading and unloading are free. All
roads are one-way and charge a toll:

| from | to | toll |
|---|---|---|
| depot | market | 3 |
| depot | station | 6 |
| depot | park | 2 |
| market | harbor | 5 |
| market | school | 4 |
| station | harbor | 2 |
| station | mill | 7 |
| park | castle | 3 |
| park | market | 2 |
| castle | mill | 2 |
| castle | farm | 4 |
| castle | hospital | 5 |
| harbor | hospital | 6 |
| harbor | bridge | 1 |
| bridge | hospital | 2 |
| bridge | airport | 3 |
| mill | school | 3 |
| mill | farm | 1 |
| farm | airport | 2 |
| farm | school | 5 |
| school | depot | 4 |
| school | hospital | 3 |
| hospital | depot | 5 |
| hospital | airport | 2 |
| hospital | mill | 4 |
| airport | depot | 3 |
| airport | station | 1 |
| airport | park | 2 |

A dispatcher proposes this plan:

1. Drive from the depot to the park.
2. Drive from the park to the castle.
3. Drive from the castle to the mill.
4. Load the books at the mill.
5. Drive from the mill to the school.
6. Unload the books at the school.
7. Drive from the school to the hospital.
8. Drive from the hospital to the airport.
9. Load the tools at the airport.
10. Drive from the airport to the station.
11. Drive from the station to the harbor.
12. Load the medicine at the harbor.
13. Drive from the harbor to the bridge.
14. Drive from the bridge to the hospital.
15. Unload the medicine at the hospital.
16. Drive from the hospital to the castle.
17. Unload the tools at the castle.
18. Drive from the castle to the farm.
19. Drive from the farm to the airport.
20. Drive from the airport to the depot.

Can the van carry out this plan as written? End your answer with one line:
`VERDICT: valid`, or `VERDICT: invalid at step N` where N is the first step
that cannot be carried out.
