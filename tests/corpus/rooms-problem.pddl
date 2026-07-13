;; Two rooms, robot starts in r1. A valid plan cleans both rooms (moving
;; between them) and then declares the job done.
(define (problem rooms-01)
  (:domain rooms)
  (:objects r1 r2 - room)
  (:init (robot-in r1))
  (:goal (done)))
