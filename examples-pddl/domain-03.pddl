;; Specification in PDDL1 of the DWR domain

(define (domain dock-worker-robot-simple)
 (:requirements :strips :typing )
 (:types 
  location      ; there are several connected locations in the harbor 
  robot         ; holds at most 1 container, only 1 robot per location
  container)

 (:predicates
   (adjacent ?l1  ?l2 - location)       ; location ?l1 is adjacent ot ?l2
   (atl ?r - robot ?l - location)       ; robot ?r is at location ?l
   (loaded ?r - robot ?c - container )  ; robot ?r is loaded with container ?c
   (unloaded ?r - robot)                ; robot ?r is empty
   (in ?c - container ?l - location)    ; container ?c is within location ?l
   )

;; there are 3 operators in this domain:

;; moves a robot between two adjacent locations
 (:action move                                
     :parameters (?r - robot ?from ?to - location)
     :precondition (and (adjacent ?from ?to) (atl ?r ?from) )
     :effect (and (atl ?r ?to)
                    (not (atl ?r ?from)) ))

;; loads an empty robot with a container held by a nearby crane
 (:action load                                
     :parameters (?l - location ?c - container ?r - robot)
     :precondition (and (atl ?r ?l) (in ?c ?l) (unloaded ?r))
     :effect (and (loaded ?r ?c)
                    (not (in ?c ?l)) (not (unloaded ?r)) ))

;; unloads a robot holding a container with a nearby crane
 (:action unload                                 
     :parameters (?l - location ?c - container ?r - robot)
     :precondition (and (atl ?r ?l) (loaded ?r ?c) )
     :effect (and (unloaded ?r) (in ?c ?l)
                    (not (loaded ?r ?c)) )) )

