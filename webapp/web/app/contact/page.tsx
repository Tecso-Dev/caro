import ContactForm from '@/components/ContactForm';

export const metadata = { title: 'تماس با ما — CARO' };

export default function ContactPage() {
  return (
    <div className="flex flex-col gap-8">
      <section>
        <p className="eyebrow">تماس با ما</p>
        <h1 className="m-0 text-[28px] font-bold leading-[1.4] max-w-[24ch]">
          سؤال، ایراد، یا اعتراض به یک عدد
        </h1>
        <p className="mt-4 mb-0 text-[15px] leading-[1.95] text-ink-2
                      max-w-[60ch]">
          اگر جایی از سامانه عددی نشان داده که فکر می‌کنی از شواهدش جلو زده،
          همان را بنویس — این نوع پیام از همه مفیدتر است.
        </p>
      </section>

      {/* The form, and what happens to a message, come from one component:
          both depend on whether this deployment keeps messages at all. */}
      <ContactForm />
    </div>
  );
}
