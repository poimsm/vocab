import type { AtlasTheme } from '@/types/atlas'

export const spaceThemes: Record<string, AtlasTheme> = {
  galaxy: {
    id: '1',
    title: 'Universe',
    description: 'Explore the structure of a galaxy',
    image: '/media/vocab/space/galaxy.png',
    items: [
  {
    id: '1',
    label: 'Sun',
    x: 9,
    y: 47,
    definition: 'The star at the center of our Solar System, providing light, heat, and gravitational pull.',
    example: 'Earth and all other planets revolve around the Sun.'
  },
  {
    id: '3',
    label: 'Comet',
    x: 55,
    y: 26,
    definition: 'An icy, small celestial body that warms up and develops a glowing coma and tail when passing near the Sun.',
    example: 'Halley is a famous comet that visits the inner solar system every 75-76 years.'
  },
  {
    id: '4',
    label: 'Orbit',
    x: 59,
    y: 73,
    definition: 'The curved path of a celestial object or spacecraft around a star, planet, or moon.',
    example: 'Earth completes one full orbit around the Sun in 365 days.'
  },
  {
    id: '5',
    label: 'Spiral Galaxy',
    x: 85,
    y: 17,
    definition: 'A rotating galaxy characterized by flattened disk systems with spiral structures extending from the center.',
    example: 'Our home galaxy, the Milky Way, is a classic example of a spiral galaxy.'
  },
  {
    id: '6',
    label: 'Asteroid Belt',
    x: 40,
    y: 68,
    definition: 'A region of space between the orbits of Mars and Jupiter filled with numerous irregularly shaped bodies.',
    example: 'Ceres is the largest object located within the asteroid belt.'
  },
  {
    id: '7',
    label: 'Distant Galaxy',
    x: 80,
    y: 80,
    definition: 'A massive system of millions or billions of stars, gas, and dark matter located far away in the observable universe.',
    example: 'Powerful telescopes like James Webb can capture light from a distant galaxy billions of light-years away.'
  },
  {
    id: '1a',
    label: 'Mercury',
    x: 20,
    y: 55,
    definition: 'The smallest and innermost planet in the Solar System, with extreme temperature fluctuations.',
    example: 'Mercury is the closest planet to the Sun.'
  },
  {
    id: '2a',
    label: 'Venus',
    x: 26,
    y: 55,
    definition: 'The second planet from the Sun, known for its thick, toxic greenhouse atmosphere and extreme surface heat.',
    example: 'Venus is often the brightest star-like object visible in the morning or evening sky.'
  },
  {
    id: '3a',
    label: 'Earth',
    x: 34,
    y: 55,
    definition: 'The third planet from the Sun and the only astronomical object known to harbor life.',
    example: 'Water covers roughly 71 percent of the surface of Earth.'
  },
  {
    id: '4a',
    label: 'Mars',
    x: 41,
    y: 55,
    definition: 'The fourth planet from the Sun, often called the Red Planet due to iron oxide prevalent on its surface.',
    example: 'Rovers like Perseverance explore the surface of Mars to search for signs of ancient life.'
  },
  {
    id: '5a',
    label: 'Jupiter',
    x: 55,
    y: 55,
    definition: 'The largest planet in the Solar System, famous for its Great Red Spot and numerous moons.',
    example: 'Jupiter is a gas giant with a mass more than two and a half times that of all other planets combined.'
  },
  {
    id: '6a',
    label: 'Saturn',
    x: 70,
    y: 55,
    definition: 'The sixth planet from the Sun, distinguished by its extensive and complex ring system made mostly of ice.',
    example: 'Saturn is the least dense planet in the Solar System; it would float in water if you had a bathtub big enough.'
  },
  {
    id: '7a',
    label: 'Uranus',
    x: 83,
    y: 55,
    definition: 'An ice giant planet with a unique sideways axial tilt that makes it rotate on its side.',
    example: 'Uranus has an extremely cold atmosphere composed mainly of hydrogen, helium, and methane.'
  },
  {
    id: '8a',
    label: 'Neptune',
    x: 92,
    y: 55,
    definition: 'The eighth and most distant major planet in the Solar System, known for its deep blue color and fierce supersonic winds.',
    example: 'Neptune takes nearly 165 Earth years to complete a single orbit around the Sun.'
  }
]
  },
  spaceship: {
    id: '2',
    title: 'Spaceship',
    description: 'Explore the parts and architecture of a spacecraft',
    image: '/media/vocab/space/ship04.png',
    items: [
      {
        id: '1',
        label: 'Airlock',
        x: 29,
        y: 47,
        definition: 'A sealed compartment that allows people to enter or leave a spacecraft without letting all the air escape.',
        example: 'The astronaut entered the airlock before going outside to repair the ship.'
      },
      {
        id: '2',
        label: 'Bunk Bed',
        x: 64,
        y: 32,
        definition: 'A set of two beds arranged one above the other, used to save space.',
        example: 'The crew members slept in bunk beds during the long journey through space.'
      },
      {
        id: '3',
        label: 'Wing',
        x: 82,
        y: 53,
        definition: 'A projecting part of a spacecraft or aircraft that can help provide stability or control.',
        example: 'The right wing was damaged when the ship passed through the asteroid field.'
      },
      {
        id: '4',
        label: 'Stabilizer Fin',
        x: 73,
        y: 12,
        definition: 'A flat surface that helps keep a vehicle stable and pointed in the right direction.',
        example: 'The stabilizer fin helped the spacecraft maintain its orientation during flight.'
      },
      {
        id: '5',
        label: 'Cockpit',
        x: 14,
        y: 50,
        definition: 'The area where a pilot sits to control and navigate a vehicle.',
        example: 'The pilot sat in the cockpit and prepared the ship for takeoff.'
      },
      {
        id: '6',
        label: 'Common Area',
        x: 50,
        y: 35,
        definition: 'A shared space where the crew can relax, eat, or spend time together.',
        example: 'The crew gathered in the common area to discuss their next mission.'
      },
      {
        id: '7',
        label: 'Cargo Hold',
        x: 56,
        y: 59,
        definition: 'A compartment in a vehicle used to store and transport goods or equipment.',
        example: 'The cargo hold was filled with supplies for the colony on Mars.'
      },
      {
        id: '8',
        label: 'Cargo Ramp',
        x: 65,
        y: 70,
        definition: 'A sloping platform that allows people or equipment to move into or out of a vehicle.',
        example: 'The crew lowered the cargo ramp to unload the supply crates.'
      },
      {
        id: '9',
        label: 'Multi-Layer Armor Hull',
        x: 20,
        y: 65,
        definition: 'The main outer body of a spacecraft that contains and protects its internal compartments.',
        example: 'The main hull protected the crew from the vacuum of space.'
      },
      {
        id: '10',
        label: 'Main Engine',
        x: 92,
        y: 25,
        definition: 'The primary propulsion system that produces the thrust needed to move a spacecraft.',
        example: 'The main engine fired, pushing the spacecraft toward the distant planet.'
      }
    ]
  },
  cockpit: {
    id: '3',
    title: 'Aliens',
    description: 'Explore different alien life forms',
    image: '/media/vocab/space/ship02.png',
    items: []
  },
  aliens: {
    id: '4',
    title: 'Aliens',
    description: 'Explore different alien life forms',
    image: '/media/vocab/space/aliens.png',
    items: []
  },
  galaxy2: {
    id: '5',
    title: 'Aliens',
    description: 'Explore different alien life forms',
    image: '/media/vocab/space/galaxy.jfif',
    items: []
  },
  space2: {
    id: '6',
    title: 'Aliens',
    description: 'Explore different alien life forms',
    image: '/media/vocab/space/spaceship.jfif',
    items: []
  }
}
