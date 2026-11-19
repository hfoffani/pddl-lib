A freight company moves packages between three cities: Madrid, Paris and
Rome. Each city has an airport and a downtown office (Madrid airport, Madrid
office, Paris airport, Paris office, Rome airport, Rome office).

Vehicles:
- one truck per city (the Madrid truck, the Paris truck, the Rome truck). A
  truck drives only between the two places of its own city.
- one airplane, which flies between any two airports.

Where things are now:
- Madrid truck: at the Madrid office. Paris truck: at Paris airport. Rome
  truck: at the Rome office. Airplane: at Rome airport.
- Package p1 is at the Madrid office, p2 at the Paris office, p3 at Paris
  airport.

Where the packages must end up: p1 at the Rome office, p2 at the Madrid
office, p3 at the Rome office. Vehicles can end anywhere.

Vehicles carry any number of packages. Each of these is one step: loading one
package into a vehicle at the place where both are, unloading one package
from a vehicle, one truck drive, one flight.

A dispatcher proposes this plan:

1. Load p1 into the Madrid truck at the Madrid office.
2. Drive the Madrid truck to Madrid airport.
3. Unload p1 at Madrid airport.
4. Drive the Madrid truck back to the Madrid office.
5. Drive the Paris truck to the Paris office.
6. Load p2 into the Paris truck.
7. Drive the Paris truck to Paris airport.
8. Unload p2 at Paris airport.
9. Drive the Rome truck to Rome airport.
10. Fly the airplane from Rome airport to Paris airport.
11. Load p2 into the airplane.
12. Load p3 into the airplane.
13. Fly the airplane to Madrid airport.
14. Load p1 into the airplane.
15. Unload p2 from the airplane at Madrid airport.
16. Load p2 into the Madrid truck at Madrid airport.
17. Drive the Madrid truck to the Madrid office.
18. Unload p2 at the Madrid office.
19. Fly the airplane to Rome airport.
20. Unload p1 from the airplane.
21. Load p1 into the Rome truck.
22. Unload p3 from the airplane.
23. Load p3 into the Rome truck.
24. Drive the Rome truck to the Rome office.
25. Unload p1 at the Rome office.
26. Unload p3 at the Rome office.

Can the company carry out this plan as written? End your answer with one
line: `VERDICT: valid`, or `VERDICT: invalid at step N` where N is the first
step that cannot be carried out.
