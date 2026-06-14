;; Same problem as blocksworld-problem.pddl but with UPPERCASE keywords,
;; as found in many real-world IPC files (#20 / #36 regression guard).
(DEFINE (PROBLEM blocksworld-01-upper)
  (:DOMAIN blocksworld)
  (:OBJECTS a b c)
  (:INIT
    (clear a) (clear b) (clear c)
    (ontable a) (ontable b) (ontable c)
    (handempty))
  (:GOAL (AND (on a b) (on b c))))
