(define (domain domain-01)
    (:requirements :strips :semantics)
    (:context op1 - uri:example/op1)
    (:action op1
        :parameters (?x1 ?x2 ?x3)
        :precondition (and (R ?x2 ?x2) (R ?x3 ?x3) (S ?x2 ?x1))
        :effect (and (R ?x2 ?x1) (S ?x1 ?x2) (not (R ?x2 ?x2)) (not (R ?x3 ?x3)) (not (S ?x2 ?x1))))
    (:action op2
        :parameters (?x1 ?x2 ?x3)
        :precondition (and (S ?x3 ?x1) (S ?x3 ?x2))
        :effect (and (R ?x2 ?x2) (R ?x3 ?x3) (not (S ?x3 ?x1)))))
