;; Logical-operators demo. Two ways to open a door:
;;  * open-door  -- a top-level DISJUNCTIVE precondition: the door opens if it is
;;                  unlocked OR the actor holds a key (precondition_connective='or').
;;  * force-door -- a conjunction with a NEGATIVE precondition: force it only if it
;;                  is not already open and it is jammed (precondition_neg non-empty).
;; Shows how the top-level connective and negative preconditions are recovered
;; into the object model (#13).
(define (domain logic)
  (:requirements :strips :disjunctive-preconditions :negative-preconditions)
  (:predicates
    (unlocked ?d)
    (has-key ?d)
    (jammed ?d)
    (open ?d))

  (:action open-door
    :parameters (?d)
    :precondition (or (unlocked ?d) (has-key ?d))
    :effect (open ?d))

  (:action force-door
    :parameters (?d)
    :precondition (and (not (open ?d)) (jammed ?d))
    :effect (open ?d)))
