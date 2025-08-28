import { AfterViewInit, ChangeDetectorRef, Component, Input } from '@angular/core';
import { MatSliderModule } from '@angular/material/slider';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-parameter-slider',
  standalone: true,
  imports: [
    MatSliderModule,
    FormsModule
  ],
  templateUrl: './parameter-slider.component.html',
  styleUrl: './parameter-slider.component.css'
})
export class ParameterSliderComponent implements AfterViewInit {
  @Input() label: string = "";
  @Input() default: number = 0;
  @Input() max: number = 0;

  constructor(private cdr: ChangeDetectorRef) {}

  selected_value: number = this.default;

  ngAfterViewInit(): void {
    this.selected_value = this.default;
    this.cdr.detectChanges();
  }

  public get(): number {
    return this.selected_value;
  }

  public displayPatameter(value: number): string {
    return value.toString() + '%';
  }
}
