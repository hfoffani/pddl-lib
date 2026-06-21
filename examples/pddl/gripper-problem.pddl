(define (problem gripper-01)
  (:domain gripper)
  (:objects
    rooma roomb - room
    ball1 ball2 - ball
    left right - gripper)
  (:init
    (at-robby rooma)
    (free left) (free right)
    (at ball1 rooma) (at ball2 rooma))
  (:goal (and (at ball1 roomb) (at ball2 roomb))))
