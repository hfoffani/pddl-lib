;; IPC Logistics (typed STRIPS): trucks move within a city, airplanes between
;; airports; packages ride in vehicles. Every action costs 1.
(define (domain logistics)
  (:requirements :strips :typing)
  (:types truck airplane - vehicle
          package vehicle - physobj
          airport location - place
          city place physobj - object)
  (:predicates (in-city ?loc - place ?city - city)
               (at ?obj - physobj ?loc - place)
               (in ?pkg - package ?veh - vehicle))

  (:action load-truck
    :parameters (?pkg - package ?truck - truck ?loc - place)
    :precondition (and (at ?truck ?loc) (at ?pkg ?loc))
    :effect (and (not (at ?pkg ?loc)) (in ?pkg ?truck)))

  (:action load-airplane
    :parameters (?pkg - package ?airplane - airplane ?loc - place)
    :precondition (and (at ?pkg ?loc) (at ?airplane ?loc))
    :effect (and (not (at ?pkg ?loc)) (in ?pkg ?airplane)))

  (:action unload-truck
    :parameters (?pkg - package ?truck - truck ?loc - place)
    :precondition (and (at ?truck ?loc) (in ?pkg ?truck))
    :effect (and (not (in ?pkg ?truck)) (at ?pkg ?loc)))

  (:action unload-airplane
    :parameters (?pkg - package ?airplane - airplane ?loc - place)
    :precondition (and (in ?pkg ?airplane) (at ?airplane ?loc))
    :effect (and (not (in ?pkg ?airplane)) (at ?pkg ?loc)))

  (:action drive-truck
    :parameters (?truck - truck ?from - place ?to - place ?city - city)
    :precondition (and (at ?truck ?from) (in-city ?from ?city) (in-city ?to ?city))
    :effect (and (not (at ?truck ?from)) (at ?truck ?to)))

  (:action fly-airplane
    :parameters (?airplane - airplane ?from - airport ?to - airport)
    :precondition (at ?airplane ?from)
    :effect (and (not (at ?airplane ?from)) (at ?airplane ?to))))
