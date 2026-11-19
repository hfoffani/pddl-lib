I am playing with a set of objects: a, b, c, d, e, f and g. Here are the
actions I can do, and their rules.

- Attack an object. Needs: the object is a province, the object is a planet,
  and there is harmony. Then: I have pain from the object; the object stops
  being a province and a planet; harmony is gone.
- Succumb to an object. Needs: I have pain from the object. Then: the object
  becomes a province and a planet; there is harmony; the pain from it is gone.
- Overcome object X from object Y. Needs: Y is a province, and I have pain from
  X. Then: there is harmony; X becomes a province; X craves Y; Y stops being a
  province; the pain from X is gone.
- Feast object X from object Y. Needs: X craves Y, X is a province, and there
  is harmony. Then: I have pain from X; Y becomes a province; X no longer
  craves Y; X stops being a province; harmony is gone.

At the start: there is harmony. e, f and d are planets. b craves e, g craves b,
a craves g, and c craves f. a, c and d are provinces.

My goal: b craves a, c craves b, d craves c, e craves d, f craves e, and g
craves f.

What is the shortest sequence of actions that reaches my goal? List every
action, e.g. "feast a from g", "attack d", "overcome d from c", "succumb to a".
