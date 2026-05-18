import { SignIn } from "@clerk/nextjs";

export default function LoginPage() {
    return (
        <div className="flex items-center justify-center min-h-screen bg-black">
            <div className="w-full max-w-md">
                <SignIn appearance={{
                    variables: {
                        colorPrimary: '#814ac8',
                    },
                    elements: {
                        formButtonPrimary: 'bg-primary hover:bg-primary/90 text-primary-foreground',
                        footerActionLink: 'text-primary hover:text-primary/90',
                        card: 'bg-zinc-900 border border-zinc-800',
                        headerTitle: 'text-zinc-100',
                        headerSubtitle: 'text-zinc-400',
                        socialButtonsBlockButton: 'text-zinc-200 border-zinc-700 hover:bg-zinc-800',
                        formFieldLabel: 'text-zinc-300',
                        formFieldInput: 'bg-zinc-950 border-zinc-800 text-zinc-200',
                        footer: 'hidden'
                    }
                }} />
            </div>
        </div>
    );
}
