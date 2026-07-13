;; A tiny cleaning domain exercising quantified preconditions
;; (:universal-preconditions) and object equality (:equality): the robot may
;; only declare the job done once *every* room is clean, and it may only move
;; between two *distinct* rooms.
(define (domain rooms)
  (:requirements :typing :negative-preconditions
                 :universal-preconditions :equality)
  (:types room)
  (:predicates
    (clean ?r - room)
    (robot-in ?r - room)
    (done))
  (:action clean-room
    :parameters (?r - room)
    :precondition (and (robot-in ?r) (not (clean ?r)))
    :effect (clean ?r))
  (:action move
    :parameters (?from - room ?to - room)
    :precondition (and (robot-in ?from) (not (= ?from ?to)))
    :effect (and (robot-in ?to) (not (robot-in ?from))))
  (:action declare-done
    :parameters ()
    :precondition (forall (?r - room) (clean ?r))
    :effect (done)))
