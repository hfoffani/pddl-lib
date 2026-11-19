;; Blocksworld with meaningless names, after PlanBench's "Mystery Blocksworld"
;; (Valmeekam et al. 2023): the physics is identical, the memorized vocabulary
;; is gone. province = clear, planet = on the table, harmony = hand empty,
;; pain = holding, craves = on; attack = pick-up, succumb = put-down,
;; overcome = stack, feast = unstack.
(define (domain mystery)
  (:requirements :strips :typing)
  (:types object)
  (:predicates (province ?x - object) (planet ?x - object) (harmony)
               (pain ?x - object) (craves ?x - object ?y - object))

  (:action attack
    :parameters (?x - object)
    :precondition (and (province ?x) (planet ?x) (harmony))
    :effect (and (pain ?x) (not (province ?x)) (not (planet ?x)) (not (harmony))))

  (:action succumb
    :parameters (?x - object)
    :precondition (pain ?x)
    :effect (and (province ?x) (planet ?x) (harmony) (not (pain ?x))))

  (:action overcome
    :parameters (?x - object ?y - object)
    :precondition (and (province ?y) (pain ?x))
    :effect (and (harmony) (province ?x) (craves ?x ?y)
                 (not (province ?y)) (not (pain ?x))))

  (:action feast
    :parameters (?x - object ?y - object)
    :precondition (and (craves ?x ?y) (province ?x) (harmony))
    :effect (and (pain ?x) (province ?y)
                 (not (craves ?x ?y)) (not (province ?x)) (not (harmony)))))
