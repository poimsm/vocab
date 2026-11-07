export interface LandingCard {
  id: string;
  title: string;
  icon: string;
  image: string;
  badge: string;
  image_height?: string;
  image_width?: string;
  image_margin_top?: string;
}

export const landingCards: LandingCard[] = [
  {
    id: 'notes-1',
    title: 'Common phrases',
    icon: 'media/landing/quotes.svg',
    image: 'media/landing/common.png',
    badge: 'akar-icons:star'
  },
  {
    id: 'notes-2a',
    title: 'Real-life uses',
    icon: 'media/landing/coffee.svg',
    image: 'media/landing/use.png',
    badge: 'akar-icons:star'
  },
  {
    id: 'notes-3',
    title: 'Word in context',
    icon: 'media/landing/document.svg',
    image: 'media/landing/context.png',
    badge: 'akar-icons:star'
  },
  // {
  //   id: 'notes-2',
  //   title: 'Meaning & vibe',
  //   icon: 'media/landing/book02.svg',
  //   image: 'media/landing/meaning.png',
  //   badge: 'akar-icons:star'
  // },  
  {
    id: 'notes-2a',
    title: 'Grow your knowledge',
    icon: 'media/landing/book.svg',
    image: 'media/landing/journey.png',
    badge: 'akar-icons:star'
  },    
  // {
  //   id: 'notes-4',
  //   title: 'Similar & opposite',
  //   icon: 'media/landing/remix.svg',
  //   image: 'media/landing/opposite.png',
  //   badge: 'akar-icons:star'
  // },
  {
    id: 'notes-7',
    title: 'Etymology',
    icon: 'media/landing/temple.svg',
    image: 'media/landing/etymology.png',    
    badge: 'akar-icons:star'
  },  
  {
    id: 'notes-6',
    title: 'Creative uses',
    icon: 'media/landing/sparkles.svg',
    image: 'media/landing/creative.png',
    image_height: "150px",
    image_margin_top: "-50px",
    badge: 'akar-icons:star'
  },
  {
    id: 'notes-5',
    title: 'Your notes',
    icon: 'media/landing/heart.svg',
    image: 'media/landing/notes.png',
    badge: 'akar-icons:star',
    image_height: "75px",
    image_margin_top: "-15px",
  },
];
