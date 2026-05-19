import { site } from "./site";

export const performPage = {
  title: "Perform with Iguana",
  description:
    "English comedy across Cancún, Playa del Carmen, Cozumel, Tulum, and more—room for touring headliners and vacationing comics alike.",
  intro: [
    "We host English-language comedy across Cancún, Playa del Carmen, Cozumel, Tulum, Puerto Morelos, Puerto Aventuras, and Mérida—working with venues, hotels, and resorts along the coast.",
    "There is space for comics at every level: industry names passing through, and comedians on holiday who want a proper room. We often trade accommodation and drinks for strong sets when the calendar allows.",
  ],
  pilgrimageHeading: "Iguana is a pilgrimage every comedian has to take once (or more) in a lifetime.",
  pilgrimageBody:
    "Mexico and the Caribbean reward comics who can read a mixed crowd—travellers, locals, hospitality staff, and the occasional wedding uncle who thinks he belongs on stage.",
  offersHeading: "What we can offer",
  formHeading: "Perform with Iguana",
  formIntro: "Tell us where you are based, what you have on tape, and when you could land. We reply from the producing desk—not a bot.",
  galleryImages: [
    site.clubPhotoImage,
    site.brandMomentImage,
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/fc28c62ff25bfe59ab4a1b77d48f063eeba57ba8c4f7605211cfd701fa7c6d27.jpg",
  ],
  formBackdrop:
    "https://files.kintana.app/workspaces/cmncfee5w000004l74ya0p0s6/blobs/e3861e77e1377e8c41284752355ab7b3b815031fcb684553d4ecb115c3e792ed.jpg",
} as const;

export const performOffers = [
  { title: "Meet new comedians" },
  { title: "Officially become an international comedian" },
  { title: "Experience Mexican culture" },
  { title: "Free accommodation in Cancún and Playa" },
  { title: "Join our wall of comedians", highlight: true },
  { title: "High quality, edited and raw footage" },
] as const;

export const performFaq = [
  {
    question: "What is performing with Iguana like?",
    answer:
      "Rooms are bilingual-friendly, run times are respected, and hosts know how to warm a travel crowd without talking down to them. You get a proper check-in, a clear stage plot, and producers who have done the work before doors open.",
    open: true,
  },
  {
    question: "How does it work?",
    answer:
      "Send your reel, passport window, and any hotel or dietary notes. We slot you into showcases, open mics, or one-off features depending on lineup needs. If you are already in town, say so—we often move faster than you expect.",
  },
  {
    question: "Will I get paid?",
    answer:
      "Headline and feature weeks are paid when the calendar is built that way. Many vacation swaps trade a tight guest set for accommodation and hospitality—we are upfront about which bucket you are in before you book flights.",
  },
] as const;
