import {
  Header,
  Hero,
  BentoFeatures,
  HowItWorks,
  BetaBanner,
  Footer,
} from '@/components/landing';
import { FeedbackFab } from '@/components/feedback';

export default function LandingPage() {
  return (
    <main
      data-testid="landing-page"
      className="min-h-screen overflow-x-hidden"
      style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
    >
      <Header />
      <Hero />
      <BentoFeatures />
      <HowItWorks />
      <BetaBanner />
      <Footer />
      <FeedbackFab />
    </main>
  );
}
