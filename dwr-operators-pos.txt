;; Specification in PDDL1 of the DWR domain

(define (domain dock-worker-robot-pos)
 (:requirements :strips :typing )
 (:types 
  location      ; there are several connected locations in the harbor 
  pile             ; is attached to a location 
                     ; it holds a pallet and a stack of containers 
  robot          ; holds at most 1 container, only 1 robot per location
  crane          ; belongs to a location to pickup containers
  container)

 (:constants
  pallet - container)

 (:predicates
   (adjacent ?l1  ?l2 - location)       ; location ?l1 is adjacent ot ?l2
   (attached ?p - pile ?l - location)  ; pile ?p attached to location ?l
   (belong ?k - crane ?l - location)   ; crane ?k belongs to location ?l

   (atl ?r - robot ?l - location)       ; robot ?r is at location ?l
   (free ?l - location)             ; there is a robot at location ?l
   (loaded ?r - robot ?c - container ) ; robot ?r is loaded with container ?c
   (unloaded ?r - robot)                 ; robot ?r is empty

   (holding ?k - crane ?c - container) ; crane ?k is holding a container ?c
   (empty ?k - crane)                          ; crane ?k is empty

   (in ?c - container ?p - pile)        ; container ?c is within pile ?p
   (top ?c - container ?p - pile)      ;  container ?c is on top of pile ?p
   (on ?k1 - container ?k2 - container); container ?k1 is on container ?k2
   )

;; there are 5 operators in this domain:

;; moves a robot between two adjacent locations
 (:action move                                
     :parameters (?r - robot ?from ?to - location)
     :precondition (and (adjacent ?from ?to)
                      (atl ?r ?from) (free ?to))
     :effect (and (atl ?r ?to) (free ?from)
		                (not (free ?to)) (not (atl ?r ?from)) ))

;; loads an empty robot with a container held by a nearby crane
 (:action load                                
     :parameters (?k - crane ?l - location ?c - container ?r - robot)
     :precondition (and (atl ?r ?l) (belong ?k ?l)
                      (holding ?k ?c) (unloaded ?r))
     :effect (and  (loaded ?r ?c) (not (unloaded ?r))
                  (empty ?k) (not (holding ?k ?c))))


;; unloads a robot holding a container with a nearby crane
 (:action unload                                 
     :parameters (?k - crane ?l - location ?c - container ?r - robot)
     :precondition (and (belong ?k ?l) (atl ?r ?l)
                      (loaded ?r ?c) (empty ?k))
     :effect (and (unloaded ?r) (holding ?k ?c)
                (not (loaded ?r ?c))(not (empty ?k))))

;; takes a container from a pile with a crane
 (:action take
     :parameters (?k - crane ?l - location ?c ?else - container ?p - pile)
     :precondition (and (belong ?k ?l)(attached ?p ?l)
                       (empty ?k) (in ?c ?p) 
                       (top ?c ?p) (on ?c ?else))
     :effect (and (holding ?k ?c) (top ?else ?p)
                (not (in ?c ?p)) (not (top ?c ?p))
                (not (on ?c ?else)) (not (empty ?k))))

;; puts a container held by a crane on a nearby pile
 (:action put                                 
     :parameters (?k - crane ?l - location ?c ?else - container ?p - pile)
     :precondition (and (belong ?k ?l) (attached ?p ?l)
                      (holding ?k ?c) (top ?else ?p))
     :effect (and (in ?c ?p) (top ?c ?p) (on ?c ?else)
                 (not (top ?else ?p)) (not (holding ?k ?c))
                 (empty ?k))))
