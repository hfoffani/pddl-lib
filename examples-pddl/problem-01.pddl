(define (problem problem-01)
    (:domain domain-01)
    (:init
        (S B B) (S C A) (S B C)
        (R B B) (R B C))
    (:goal (and (R C C))))
