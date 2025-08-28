import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ParameterSliderComponent } from './parameter-slider.component';

describe('ParameterSliderComponent', () => {
  let component: ParameterSliderComponent;
  let fixture: ComponentFixture<ParameterSliderComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ParameterSliderComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(ParameterSliderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
