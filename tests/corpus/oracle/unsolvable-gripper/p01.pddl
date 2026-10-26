; Unsolvable on purpose (#153): picking a ball deletes (at ?b ?room), so
; it is never in two rooms at once. The domain is IPC-1998 gripper.
(define (problem unsolvable-gripper)
   (:domain gripper-strips)
   (:objects rooma roomb ball1 left)
   (:init (room rooma) (room roomb) (ball ball1) (gripper left)
          (at-robby rooma) (free left) (at ball1 rooma))
   (:goal (and (at ball1 rooma) (at ball1 roomb))))
